import io
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import document_generator as docs
from web_app import create_app


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"OPENAI_API_KEY": "", "OPENAI_BASE_URL": "http://localhost:3000/v1"})
        self.env.start()
        self.app = create_app(Path(self.temp.name))
        self.client = self.app.test_client()
        self.studio = self.app.extensions["studio"]
        self.headers = {"X-Studio-Token": self.studio.token}

    def tearDown(self):
        self.studio.close()
        self.env.stop()
        self.temp.cleanup()

    def post(self, path, data):
        return self.client.post(path, json=data, headers=self.headers)

    def start(self, **kwargs):
        response = self.post("/api/tasks", {"render_mode": "local", "profile_id": "default", **kwargs})
        self.assertEqual(response.status_code, 202, response.get_json())
        return response.get_json()["id"]

    def wait(self, task_id):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            response = self.client.get(f"/api/tasks/{task_id}")
            self.assertEqual(response.status_code, 200, response.get_json())
            task = response.get_json()
            if task["status"] in ("complete", "failed"):
                return task
            time.sleep(.025)
        self.fail("Generation did not finish")

    def test_bootstrap_and_assets(self):
        result = self.client.get("/api/bootstrap")
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.get_json()["key_configured"])
        self.assertEqual(result.get_json()["settings"]["model"], "gpt-image-2")
        self.assertIn("default-src 'self'", result.headers["Content-Security-Policy"])
        for path in ("/", "/static/app.js", "/static/app.css", "/static/lucide.min.js"):
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 200)

    def test_local_generation_preview_and_bundle(self):
        task = self.wait(self.start())
        self.assertEqual(task["status"], "complete", task)
        batch_id = task["batch_id"]
        batch = self.client.get(f"/api/batches/{batch_id}").get_json()
        self.assertEqual(batch["outputs_done"], 3)
        self.assertEqual(batch["render_mode"], "local")
        self.assertEqual(batch["presentation"], "code_v2")
        self.assertEqual(batch["assets_total"], 1)
        for kind in docs.SIZES:
            with self.client.get(f"/api/batches/{batch_id}/image/{kind}") as image:
                self.assertEqual(image.status_code, 200)
                self.assertEqual(image.mimetype, "image/png")
                self.assertTrue(image.data.startswith(b"\x89PNG"))
        bundle = self.client.get(f"/api/batches/{batch_id}/download")
        self.assertEqual(bundle.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(bundle.data)) as archive:
            self.assertEqual(len(archive.namelist()), 5)
            self.assertIn("sources.json", archive.namelist())
            self.assertIn("profile.json", archive.namelist())
        self.assertEqual(len(self.client.get("/api/batches").get_json()), 1)

    def test_repeated_generation_creates_history_batches(self):
        first = self.wait(self.start(fresh_profile=True))
        second = self.wait(self.start(fresh_profile=True))
        self.assertEqual(first["status"], "complete")
        self.assertEqual(second["status"], "complete")
        self.assertNotEqual(first["batch_id"], second["batch_id"])
        self.assertNotEqual(first["batch"]["profile"]["full_name"], second["batch"]["profile"]["full_name"])
        self.assertNotEqual(first["batch"]["profile"]["student_id"], second["batch"]["profile"]["student_id"])
        for task in (first, second):
            job = docs.read_json(self.studio.batch_path(task["batch_id"]) / "job.json")
            for output in job["outputs"].values():
                self.assertIn(task["batch"]["profile"]["full_name"], [item["text"] for item in output["rendered_text"]])
        batches = self.client.get("/api/batches").get_json()
        self.assertEqual(len(batches), 2)
        self.assertEqual({batch["status"] for batch in batches}, {"complete"})

    def test_fresh_ai_batch_saves_photorealistic_portrait(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "TEST_ONLY"}):
            with patch.object(docs, "make_ai_image", return_value=docs.local_asset("portrait")) as generator:
                task = self.wait(self.start(fresh_profile=True, render_mode="ai"))
        self.assertEqual(task["status"], "complete", task)
        self.assertIn("Photorealistic", generator.call_args_list[0].args[0])
        self.assertIn("entirely fictional", generator.call_args_list[0].args[0])
        self.assertEqual(generator.call_args_list[0].args[3], "gpt-image-2")
        path = self.studio.profile_image_path(task["profile"]["id"])
        self.assertEqual(docs.digest(path), docs.digest(self.studio.batch_path(task["batch_id"]) / "asset_portrait.png"))

    def test_profiles_are_copies_and_age_checked(self):
        original = docs.digest(Path(self.temp.name) / "profile.json")
        response = self.post("/api/profiles", {"full_name": "Taylor Brooks", "date_of_birth": "2005-06-15"})
        self.assertEqual(response.status_code, 201)
        profile = response.get_json()
        self.assertEqual(profile["age"], 21)
        self.assertEqual(profile["country"], "United States")
        self.assertEqual(docs.digest(Path(self.temp.name) / "profile.json"), original)
        random_profile = self.post("/api/profiles", {})
        self.assertEqual(random_profile.status_code, 201)
        self.assertNotEqual(random_profile.get_json()["id"], profile["id"])
        invalid = self.post("/api/profiles", {"full_name": "Taylor Brooks", "date_of_birth": "2015-06-15"})
        self.assertEqual(invalid.status_code, 400)
        task = self.wait(self.start(profile_id=profile["id"]))
        self.assertEqual(task["batch"]["profile"]["full_name"], "Taylor Brooks")

    def test_zip_upload_validation(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("README-UMGC-resources.md", "Public references")
        buffer.seek(0)
        uploaded = self.client.post("/api/resources", data={"file": (buffer, "school.zip")}, headers=self.headers)
        self.assertEqual(uploaded.status_code, 201, uploaded.get_json())
        task = self.wait(self.start(resource_id=uploaded.get_json()["id"]))
        self.assertEqual(task["status"], "complete", task)
        path = self.studio.batch_path(task["batch_id"]) / "sources.json"
        self.assertTrue(docs.read_json(path)["supplied_resources"]["provided"])
        invalid = self.client.post("/api/resources", data={"file": (io.BytesIO(b"not zip"), "bad.zip")}, headers=self.headers)
        self.assertEqual(invalid.status_code, 400)
        traversal = io.BytesIO()
        with zipfile.ZipFile(traversal, "w") as archive:
            archive.writestr("../escape", "bad")
        traversal.seek(0)
        invalid = self.client.post("/api/resources", data={"file": (traversal, "bad.zip")}, headers=self.headers)
        self.assertEqual(invalid.status_code, 400)

    def test_csrf_origin_and_dns_rebinding(self):
        self.assertEqual(self.client.post("/api/profiles", json={}).status_code, 403)
        self.assertEqual(self.client.post("/api/profiles", json={}, headers={**self.headers, "Origin": "https://evil.example"}).status_code, 403)
        self.assertEqual(self.client.get("/api/bootstrap", headers={"Host": "evil.example"}).status_code, 403)
        self.assertEqual(self.client.get("/api/bootstrap", headers={"Sec-Fetch-Site": "cross-site"}).status_code, 403)
        self.assertEqual(self.client.get("/static/../profile.json").status_code, 404)
        self.assertEqual(self.client.get("/api/batches/invalid").status_code, 400)

    def test_credentials_never_returned_or_saved(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "SERVER_ONLY_TEST_KEY"}):
            response = self.client.get("/api/bootstrap")
            self.assertTrue(response.get_json()["key_configured"])
            self.assertNotIn("SERVER_ONLY_TEST_KEY", response.get_data(as_text=True))
            settings = {"base_url": "http://localhost:3000/v1", "model": "gpt-image-2", "timeout": 50, "api_key": "DO_NOT_SAVE"}
            self.assertEqual(self.post("/api/settings", settings).status_code, 200)
            saved = (self.studio.storage / "settings.json").read_text()
            self.assertNotIn("api_key", saved)
            self.assertNotIn("DO_NOT_SAVE", saved)

    def test_ai_requires_server_key(self):
        result = self.post("/api/tasks", {"render_mode": "ai"})
        self.assertEqual(result.status_code, 400)
        self.assertIn("OPENAI_API_KEY", result.get_json()["error"])
        self.assertEqual(self.studio.batches(), [])

    def test_profile_portrait_requires_server_key(self):
        result = self.post("/api/profiles/default/portrait", {"settings": {"base_url": "http://localhost:3000/v1",
                                                                            "model": "gpt-image-2", "timeout": 50}})
        self.assertEqual(result.status_code, 400)
        self.assertIn("OPENAI_API_KEY", result.get_json()["error"])

    def test_profile_portrait_uses_ai_model_and_stays_server_side(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "SERVER_ONLY_TEST_KEY"}):
            with patch.object(docs, "make_ai_image", return_value=docs.local_asset("portrait")) as generator:
                result = self.post("/api/profiles/default/portrait", {"settings": {"base_url": "http://localhost:3000/v1",
                                                                                    "model": "gpt-image-2", "timeout": 50}})
        self.assertEqual(result.status_code, 201, result.get_json())
        profile = result.get_json()
        self.assertEqual(profile["id"], "default")
        self.assertEqual(profile["portrait_url"], "/api/profiles/default/portrait")
        self.assertNotIn("SERVER_ONLY_TEST_KEY", result.get_data(as_text=True))
        generator.assert_called_once()
        self.assertEqual(generator.call_args.args[3], "gpt-image-2")
        with self.client.get(profile["portrait_url"]) as image:
            self.assertEqual(image.status_code, 200)
            self.assertEqual(image.mimetype, "image/png")
        bootstrap = self.client.get("/api/bootstrap").get_json()
        default_profile = next(item for item in bootstrap["profiles"] if item["id"] == "default")
        self.assertEqual(default_profile["portrait_url"], "/api/profiles/default/portrait")

    def test_ai_failure_retry_preserves_cached_asset_and_model(self):
        import document_layouts
        original = document_layouts.render_code_v2
        def interrupted(kind, *args):
            if kind == "student_card":
                raise RuntimeError("render failure")
            return original(kind, *args)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "SERVER_ONLY_TEST_KEY"}):
            with patch.object(docs, "make_ai_image", return_value=docs.local_asset("portrait")):
                with patch.object(document_layouts, "render_code_v2", side_effect=interrupted):
                    first = self.wait(self.start(render_mode="ai"))
            self.assertEqual(first["status"], "failed")
            self.assertNotIn("SERVER_ONLY_TEST_KEY", first["error"])
            cached = self.studio.batch_path(first["batch_id"]) / "asset_portrait.png"
            before = cached.stat().st_mtime_ns
            with patch.object(docs, "make_ai_image", side_effect=RuntimeError("should not generate a new portrait")) as generator:
                second = self.wait(self.start(resume_id=first["batch_id"]))
            self.assertEqual(second["status"], "complete", second)
            generator.assert_not_called()
            self.assertEqual(cached.stat().st_mtime_ns, before)

    def test_ai_asset_failure_can_resume_with_same_model(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "SERVER_ONLY_TEST_KEY"}):
            with patch.object(docs, "make_ai_image", side_effect=RuntimeError("unsupported model SERVER_ONLY_TEST_KEY")):
                first = self.wait(self.start(render_mode="ai"))
            self.assertEqual(first["status"], "failed")
            self.assertNotIn("SERVER_ONLY_TEST_KEY", first["error"])
            with patch.object(docs, "make_ai_image", return_value=docs.local_asset("portrait")) as generator:
                second = self.wait(self.start(resume_id=first["batch_id"]))
            self.assertEqual(second["status"], "complete", second)
            generator.assert_called_once()
            self.assertEqual(generator.call_args.args[3], "gpt-image-2")

    def test_one_active_task_and_bad_settings(self):
        self.studio.busy.acquire()
        try:
            self.assertEqual(self.post("/api/tasks", {"render_mode": "local"}).status_code, 409)
        finally:
            self.studio.busy.release()
        bad = {"base_url": "https://example.test/v1?token=SECRET", "model": "gpt-image-2", "timeout": 300}
        self.assertEqual(self.post("/api/settings", bad).status_code, 400)
        self.assertEqual(self.post("/api/tasks", {"profile_id": "../../outside"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
