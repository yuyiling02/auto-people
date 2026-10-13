"""Loopback-only document studio. API credentials remain in the server environment."""

import argparse
import atexit
import io
import os
import re
import secrets
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, abort, jsonify, request, send_file
from werkzeug.exceptions import HTTPException
from werkzeug.serving import make_server

import document_generator as docs
from image_api import checked_url

ROOT = Path(__file__).resolve().parent
BATCH_ID = re.compile(r"\d{8}T\d{6}Z-[a-f0-9]{8}\Z")
ID = re.compile(r"[a-f0-9]{32}\Z")


def load_local_env():
    path = ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def public_error(error):
    message = str(error).split("\nResume with", 1)[0]
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        message = message.replace(key, "[REDACTED]")
    return message[:800]


class Studio:
    def __init__(self, root, resource_zip=None):
        self.root = Path(root).resolve()
        self.outputs = self.root / "outputs"
        self.storage = self.outputs / ".studio"
        for name in ("profiles", "profile-images", "resources", "tasks"):
            (self.storage / name).mkdir(parents=True, exist_ok=True)
        self.source = docs.read_json(docs.SNAPSHOT)
        docs.get_profile(self.root / "profile.json", self.source["session"])
        self.provided_zip = Path(resource_zip).resolve() if resource_zip else None
        self.token = secrets.token_urlsafe(32)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="document-studio")
        self.lock = threading.RLock()
        self.busy = threading.Lock()
        self.active_id = None
        self.tasks = {}
        for path in (self.storage / "tasks").glob("*.json"):
            try:
                task = docs.read_json(path)
                if task["status"] in ("queued", "running"):
                    task.update(status="failed", error="The server stopped during this batch. Check the batch before retrying.")
                self.tasks[task["id"]] = task
            except (OSError, ValueError, KeyError):
                continue

    def close(self):
        self.executor.shutdown(wait=True)

    def settings(self):
        defaults = {"base_url": os.environ.get("OPENAI_BASE_URL", "http://localhost:3000/v1"),
                    "model": "gpt-image-2", "timeout": 300}
        path = self.storage / "settings.json"
        if path.exists():
            defaults.update(docs.read_json(path))
        return self.validate_settings(defaults)

    def validate_settings(self, data):
        base_url = str(data.get("base_url", "")).strip().rstrip("/")
        parsed = urlsplit(checked_url(base_url))
        if parsed.query or parsed.fragment:
            raise ValueError("API base URL cannot contain query parameters, tokens or fragments.")
        model = str(data.get("model", "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,100}", model):
            raise ValueError("Enter a valid image model name.")
        try:
            timeout = float(data.get("timeout", 300))
        except (ValueError, TypeError):
            raise ValueError("Timeout must be a number between 1 and 600 seconds.") from None
        if not 1 <= timeout <= 600:
            raise ValueError("Timeout must be between 1 and 600 seconds.")
        return {"base_url": base_url, "model": model, "timeout": timeout}

    def profile_path(self, profile_id):
        if profile_id == "default":
            return self.root / "profile.json"
        if not isinstance(profile_id, str) or not ID.fullmatch(profile_id):
            raise ValueError("Unknown profile.")
        path = self.storage / "profiles" / f"{profile_id}.json"
        if not path.is_file():
            raise ValueError("Unknown profile.")
        return path

    def profile_image_path(self, profile_id):
        if profile_id == "default":
            return self.storage / "profile-images" / "default.png"
        if not isinstance(profile_id, str) or not ID.fullmatch(profile_id):
            raise ValueError("Unknown profile.")
        self.profile_path(profile_id)
        return self.storage / "profile-images" / f"{profile_id}.png"

    def profiles(self):
        entries = [("default", self.root / "profile.json")]
        entries += [(p.stem, p) for p in sorted((self.storage / "profiles").glob("*.json"),
                                              key=lambda p: p.stat().st_mtime, reverse=True)]
        result = []
        for profile_id, path in entries:
            profile = docs.read_json(path)
            docs.validate_profile(profile, self.source["session"])
            image_path = self.profile_image_path(profile_id)
            result.append({**profile, "id": profile_id,
                           "age": docs.age_on(profile["date_of_birth"], self.source["session"]["start"]),
                           "portrait_url": f"/api/profiles/{profile_id}/portrait" if image_path.is_file() else ""})
        return result

    def create_profile(self, data):
        profile_id = uuid.uuid4().hex
        path = self.storage / "profiles" / f"{profile_id}.json"
        if data:
            if not isinstance(data.get("full_name"), str):
                raise ValueError("Full name must be an English name.")
            profile = {"schema_version": 1, "fictional": True,
                       "full_name": data.get("full_name", "").strip(),
                       "date_of_birth": data.get("date_of_birth"), "country": "United States",
                       "student_id": "DEMO-" + uuid.uuid4().hex[:8].upper()}
            docs.validate_profile(profile, self.source["session"])
            docs.write_json(path, profile)
        else:
            profile, _ = docs.get_profile(path, self.source["session"])
        return {**profile, "id": profile_id,
                "age": docs.age_on(profile["date_of_birth"], self.source["session"]["start"]),
                "portrait_url": ""}

    def profile(self, profile_id):
        profile = docs.read_json(self.profile_path(profile_id))
        docs.validate_profile(profile, self.source["session"])
        image_path = self.profile_image_path(profile_id)
        return {**profile, "id": profile_id,
                "age": docs.age_on(profile["date_of_birth"], self.source["session"]["start"]),
                "portrait_url": f"/api/profiles/{profile_id}/portrait" if image_path.is_file() else ""}

    def generate_profile_portrait(self, profile_id, settings):
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is not configured on the server. Set it and restart the studio.")
        profile = docs.read_json(self.profile_path(profile_id))
        docs.validate_profile(profile, self.source["session"])
        prompt = docs.asset_prompts(profile, self.source["session"])["portrait"]
        image = docs.make_ai_image(prompt, settings["base_url"], os.environ.get("OPENAI_API_KEY"),
                                   settings["model"], "1024x1024", settings["timeout"])
        path = self.profile_image_path(profile_id)
        docs.save_image(image, path)
        return self.profile(profile_id)

    def resources(self):
        items = []
        if self.provided_zip and self.provided_zip.is_file():
            items.append({"id": "provided", "name": self.provided_zip.name,
                          "bytes": self.provided_zip.stat().st_size})
        for path in sorted((self.storage / "resources").glob("*.json")):
            items.append(docs.read_json(path))
        return items

    def resource_path(self, resource_id):
        if not resource_id:
            return None
        if resource_id == "provided" and self.provided_zip and self.provided_zip.is_file():
            return self.provided_zip
        if not isinstance(resource_id, str) or not ID.fullmatch(resource_id):
            raise ValueError("Unknown resource package.")
        path = self.storage / "resources" / f"{resource_id}.zip"
        if not path.is_file():
            raise ValueError("Unknown resource package.")
        return path

    def add_resource(self, upload):
        if not upload.filename or not upload.filename.lower().endswith(".zip"):
            raise ValueError("Choose a ZIP resource package.")
        resource_id = uuid.uuid4().hex
        path = self.storage / "resources" / f"{resource_id}.zip"
        upload.save(path)
        try:
            info = docs.inspect_resource_zip(path)
        except Exception:
            path.unlink(missing_ok=True)
            raise ValueError("Invalid ZIP, unsafe member path or package larger than 10 MB.") from None
        metadata = {"id": resource_id, "name": Path(upload.filename.replace("\\", "/")).name[:160],
                    "bytes": path.stat().st_size, "entries": len(info["entries"])}
        docs.write_json(path.with_suffix(".json"), metadata)
        return metadata

    def batch_path(self, batch_id):
        if not isinstance(batch_id, str) or not BATCH_ID.fullmatch(batch_id):
            raise ValueError("Unknown batch.")
        path = self.outputs / batch_id
        if path.resolve().parent != self.outputs.resolve() or not (path / "job.json").is_file():
            raise ValueError("Unknown batch.")
        return path

    def batch(self, batch_id):
        path = self.batch_path(batch_id)
        job = docs.read_json(path / "job.json")
        inputs = docs.read_json(path / "inputs.json")
        files = {}
        for kind, record in job.get("outputs", {}).items():
            if kind in docs.SIZES:
                files[kind] = {"name": record["file"], "size": record["size"],
                               "url": f"/api/batches/{batch_id}/image/{kind}"}
        status = job["status"]
        with self.lock:
            active = self.tasks.get(self.active_id, {})
            if status in ("created", "running") and active.get("batch_id") != batch_id:
                status = "interrupted"
        return {"id": batch_id, "created": datetime.strptime(batch_id[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat(),
                "status": status, "profile": inputs["profile"], "render_mode": inputs["render_mode"],
                "model": inputs["model"], "assets_done": len(job.get("assets", {})),
                "assets_total": len(inputs.get("prompts", {})), "outputs_done": len(files), "outputs_total": len(docs.SIZES),
                "presentation": inputs.get("presentation", "flat"),
                "files": files, "error": public_error(job.get("error", ""))}

    def batches(self):
        result = []
        for path in sorted(self.outputs.iterdir(), reverse=True):
            if BATCH_ID.fullmatch(path.name):
                try:
                    result.append(self.batch(path.name))
                except (OSError, ValueError, KeyError):
                    continue
        return result

    def artifact(self, batch_id, kind):
        if kind not in docs.SIZES:
            raise ValueError("Unknown document type.")
        path = self.batch_path(batch_id)
        job = docs.read_json(path / "job.json")
        if kind not in job.get("outputs", {}):
            raise ValueError("This document is not ready yet.")
        return docs.verified_existing(path, job["outputs"][kind])

    def save_task(self, task):
        with self.lock:
            self.tasks[task["id"]] = dict(task)
            docs.write_json(self.storage / "tasks" / (task["id"] + ".json"), task)

    def get_task(self, task_id):
        with self.lock:
            if task_id not in self.tasks:
                raise ValueError("Unknown generation task.")
            task = dict(self.tasks[task_id])
        if task.get("batch_id"):
            task["batch"] = self.batch(task["batch_id"])
        return task

    def start_task(self, data):
        settings = self.validate_settings(data.get("settings", self.settings()))
        resume_id = data.get("resume_id")
        if resume_id:
            batch = self.batch(resume_id)
            if batch["status"] == "complete":
                raise ValueError("This batch is already complete.")
            mode = batch["render_mode"]
            options = {"resume": self.batch_path(resume_id)}
        else:
            mode = data.get("render_mode", "local")
            if mode not in ("ai", "local"):
                raise ValueError("Unknown rendering mode.")
            options = {"profile_path": self.profile_path(data.get("profile_id", "default")),
                       "resource_zip": self.resource_path(data.get("resource_id", "")), "render_mode": mode}
        if mode == "ai" and not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is not configured on the server. Set it and restart the studio.")
        if not self.busy.acquire(blocking=False):
            abort(409, "Another generation task is already running.")
        task = {"id": uuid.uuid4().hex, "status": "queued", "batch_id": resume_id,
                "created": stamp(), "error": ""}
        try:
            if not resume_id and data.get("fresh_profile", False):
                used = {p["full_name"] for p in self.profiles()}
                for _ in range(128):
                    profile = self.create_profile({})
                    if profile["full_name"] not in used:
                        break
                    self.profile_path(profile["id"]).unlink()
                else:
                    raise ValueError("Could not create a distinct fictional name. Try again.")
                options["profile_path"] = self.profile_path(profile["id"])
                task["profile"] = profile
            self.save_task(task)
            with self.lock:
                self.active_id = task["id"]
            self.executor.submit(self.run_task, task, options, settings)
        except Exception:
            with self.lock:
                self.active_id = None
            self.busy.release()
            raise
        return task

    def run_task(self, task, options, settings):
        def on_batch(path):
            task["batch_id"] = path.name
            self.save_task(task)

        try:
            task["status"] = "running"
            self.save_task(task)
            docs.generate_document_set(**options, out_dir=self.outputs, **settings,
                                       api_key=os.environ.get("OPENAI_API_KEY"), on_batch=on_batch)
            if task.get("profile") and options.get("render_mode") == "ai":
                with docs.Image.open(self.batch_path(task["batch_id"]) / "asset_portrait.png") as image:
                    docs.save_image(image, self.profile_image_path(task["profile"]["id"]))
            task.update(status="complete", error="")
        except Exception as error:
            task.update(status="failed", error=public_error(error))
        finally:
            try:
                self.save_task(task)
            finally:
                with self.lock:
                    self.active_id = None
                self.busy.release()


def create_app(root=ROOT, resource_zip=None):
    app = Flask(__name__, static_folder=None)
    app.config.update(MAX_CONTENT_LENGTH=11 * 1024 * 1024)
    studio = Studio(root, resource_zip)
    app.extensions["studio"] = studio

    @app.before_request
    def local_requests_only():
        port = request.environ.get("SERVER_PORT", "80")
        hosts = {"localhost", "127.0.0.1", f"localhost:{port}", f"127.0.0.1:{port}"}
        if request.host not in hosts or request.headers.get("Sec-Fetch-Site") == "cross-site":
            abort(403, "This studio only accepts local same-origin requests.")
        if request.method != "GET" and request.method != "HEAD":
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                abort(403, "Cross-origin requests are not allowed.")
            if not secrets.compare_digest(request.headers.get("X-Studio-Token", ""), studio.token):
                abort(403, "Refresh the studio before submitting this request.")

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(Exception)
    def error_response(error):
        status = error.code if isinstance(error, HTTPException) else 400 if isinstance(error, (ValueError, KeyError)) else 500
        message = error.description if isinstance(error, HTTPException) else public_error(error)
        return jsonify(error=message), status

    def payload():
        if request.content_length and request.content_length > 8192:
            abort(413, "Request is too large.")
        value = request.get_json()
        if not isinstance(value, dict):
            raise ValueError("Request must be a JSON object.")
        return value

    @app.get("/")
    def index():
        return send_file(ROOT / "web" / "index.html")

    @app.get("/favicon.ico")
    def favicon():
        return "", 204

    @app.get("/static/<name>")
    def static_file(name):
        if name not in {"app.css", "app.js", "lucide.min.js"}:
            abort(404)
        return send_file(ROOT / "web" / name)

    @app.get("/api/bootstrap")
    def bootstrap():
        return jsonify(token=studio.token, settings=studio.settings(),
                       key_configured=bool(os.environ.get("OPENAI_API_KEY")), profiles=studio.profiles(),
                       resources=studio.resources(), sources=studio.source, batches=studio.batches(),
                       active_task=studio.active_id)

    @app.post("/api/settings")
    def settings():
        value = studio.validate_settings(payload())
        with studio.lock:
            docs.write_json(studio.storage / "settings.json", value)
        return jsonify(value)

    @app.post("/api/profiles")
    def create_profile():
        return jsonify(studio.create_profile(payload())), 201

    @app.post("/api/profiles/<profile_id>/portrait")
    def create_profile_portrait(profile_id):
        value = studio.validate_settings(payload().get("settings", studio.settings()))
        return jsonify(studio.generate_profile_portrait(profile_id, value)), 201

    @app.get("/api/profiles/<profile_id>/portrait")
    def profile_portrait(profile_id):
        path = studio.profile_image_path(profile_id)
        if not path.is_file():
            raise ValueError("No generated student image is available for this profile.")
        return send_file(path, mimetype="image/png")

    @app.post("/api/resources")
    def upload_resource():
        if "file" not in request.files:
            raise ValueError("Choose a resource ZIP.")
        return jsonify(studio.add_resource(request.files["file"])), 201

    @app.post("/api/tasks")
    def create_task():
        return jsonify(studio.start_task(payload())), 202

    @app.get("/api/tasks/<task_id>")
    def task(task_id):
        return jsonify(studio.get_task(task_id))

    @app.get("/api/batches")
    def batches():
        return jsonify(studio.batches())

    @app.get("/api/batches/<batch_id>")
    def batch(batch_id):
        return jsonify(studio.batch(batch_id))

    @app.get("/api/batches/<batch_id>/image/<kind>")
    def image(batch_id, kind):
        return send_file(studio.artifact(batch_id, kind), mimetype="image/png",
                         as_attachment=request.args.get("download") == "1")

    @app.get("/api/batches/<batch_id>/sources")
    def sources(batch_id):
        path = studio.batch_path(batch_id)
        return send_file(path / "sources.json", mimetype="application/json", as_attachment=True)

    @app.get("/api/batches/<batch_id>/download")
    def download(batch_id):
        batch = studio.batch(batch_id)
        if batch["status"] != "complete":
            raise ValueError("The three-document set is not complete yet.")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for kind in docs.SIZES:
                path = studio.artifact(batch_id, kind)
                archive.write(path, path.name)
            for name in ("profile.json", "sources.json"):
                archive.write(studio.batch_path(batch_id) / name, name)
        buffer.seek(0)
        return send_file(buffer, mimetype="application/zip", as_attachment=True,
                         download_name=f"umgc-{batch_id}.zip")

    return app


def main():
    parser = argparse.ArgumentParser(description="UMGC local document studio")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--resource-zip", default=None)
    args = parser.parse_args()
    app = create_app(resource_zip=args.resource_zip)
    atexit.register(app.extensions["studio"].close)
    for port in range(args.port, min(args.port + 20, 65536)):
        try:
            server = make_server("127.0.0.1", port, app, threaded=True)
            break
        except (OSError, SystemExit):
            continue
    else:
        raise RuntimeError("No available local port in the requested range.")
    print(f"UMGC Document Studio: http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
