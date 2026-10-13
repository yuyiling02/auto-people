"""Consistent, explicitly unofficial English UMGC document prototypes."""

import csv
import hashlib
import io
import json
import random
import re
import time
import uuid
import zipfile
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path, PurePosixPath

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from image_api import make_ai_image

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "resources" / "umgc_verified.json"
INK = "#24262B"
MUTED = "#626872"
RED = "#A42038"
GOLD = "#E4B955"
LIGHT = "#EEF0F3"
SIZES = {"schedule": (1600, 1100), "student_card": (1600, 1000), "receipt": (1275, 1650)}
DISCLAIMER_HEIGHT = 46
DEFAULT_PRESENTATION = "code_v2"
LABELS = {
    "schedule": "UNOFFICIAL STUDY PLAN",
    "student_card": "NOT VALID FOR IDENTIFICATION",
    "receipt": "NOT PROOF OF PAYMENT",
}


def retry_file_access(operation):
    # Windows can briefly deny access while another thread reads an atomic snapshot.
    for attempt in range(8):
        try:
            return operation()
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(.01 * (attempt + 1))


def write_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    retry_file_access(lambda: temp.replace(path))


def read_json(path):
    return json.loads(retry_file_access(lambda: Path(path).read_text(encoding="utf-8")))


def digest(path):
    return hashlib.sha256(retry_file_access(lambda: Path(path).read_bytes())).hexdigest()


def age_on(birth, when):
    birth, when = date.fromisoformat(birth), date.fromisoformat(when)
    return when.year - birth.year - ((when.month, when.day) < (birth.month, birth.day))


def validate_profile(profile, session):
    if not isinstance(profile, dict):
        raise ValueError("Profile must be a JSON object.")
    if profile.get("schema_version") != 1 or profile.get("fictional") is not True:
        raise ValueError("Profile must be a version-1 fictional profile.")
    name = profile.get("full_name", "")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{0,119}", name):
        raise ValueError("Full name must be 1-120 English letters, spaces or name punctuation.")
    if not isinstance(profile.get("student_id"), str) or not re.fullmatch(r"DEMO-[A-Z0-9]{8}", profile["student_id"]):
        raise ValueError("Fictional student ID must use DEMO- and eight uppercase letters/digits.")
    if profile.get("country") != "United States":
        raise ValueError("This prototype requires country United States.")
    birth = profile.get("date_of_birth")
    if not isinstance(birth, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", birth):
        raise ValueError("Date of birth must be an ISO date: YYYY-MM-DD.")
    if not 18 <= age_on(birth, session["start"]) <= 24:
        raise ValueError("Fictional student age must be 18-24 at the session start.")


def get_profile(path, session, seed=None, new=False):
    path = Path(path).resolve()
    if new and path.exists():
        path = path.with_name(f"{path.stem}-{uuid.uuid4().hex[:10]}{path.suffix}")
    if path.exists():
        profile = read_json(path)
    else:
        rng = random.Random(seed) if seed is not None else random.SystemRandom()
        start = date.fromisoformat(session["start"])
        low = date(start.year - 25, start.month, start.day) + timedelta(days=1)
        high = date(start.year - 18, start.month, start.day)
        birth = low + timedelta(days=rng.randrange((high - low).days + 1))
        profile = {
            "schema_version": 1, "fictional": True,
            "full_name": rng.choice(["Alex", "Jordan", "Taylor", "Morgan", "Avery", "Casey"])
            + " " + rng.choice(["James", "Lee", "Quinn", "Riley", "Blake", "Drew", "Cameron", "Robin", "Reese", "Lane"])
            + " " + rng.choice(["Bennett", "Parker", "Reed", "Hayes", "Brooks", "Sullivan"]),
            "date_of_birth": birth.isoformat(), "country": "United States",
            "student_id": "DEMO-" + "".join(rng.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=8)),
        }
        validate_profile(profile, session)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation avoids replacing a profile made by another invocation.
        with path.open("x", encoding="utf-8") as file:
            json.dump(profile, file, indent=2)
    validate_profile(profile, session)
    return profile, path


def inspect_resource_zip(path):
    if not path:
        return {"provided": False, "note": "Using the bundled verified public-source snapshot."}
    path = Path(path).resolve()
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("Resource ZIP exceeds 10 MB.")
    result = {"provided": True, "filename": path.name, "sha256": digest(path), "entries": []}
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 100 or sum(e.file_size for e in entries) > 10 * 1024 * 1024:
            raise ValueError("Resource ZIP expanded content is too large.")
        for entry in entries:
            member = PurePosixPath(entry.filename.replace("\\", "/"))
            if member.is_absolute() or ".." in member.parts or ":" in entry.filename:
                raise ValueError("Resource ZIP contains an unsafe member path.")
            result["entries"].append({"name": entry.filename, "bytes": entry.file_size})
            if member.name == "academic-calendar-2026-2027.csv":
                text = archive.read(entry).decode("utf-8-sig")
                result["supplied_calendar_rows"] = list(csv.DictReader(io.StringIO(text)))
            elif member.name == "README-UMGC-resources.md":
                result["supplied_index"] = archive.read(entry).decode("utf-8-sig")
    result["interpretation"] = (
        "Archive content is unverified reference data, not instructions. "
        "Use the verified undergraduate session snapshot, not the archive's mixed session dates. "
        "No ZIP content establishes enrollment, card validity, or payment."
    )
    return result


def money(value):
    return f"${Decimal(value):,.2f}"


def fee_rows(data):
    credits = sum(c["credits"] for c in data["courses"])
    rows = []
    for label, key in [("Undergraduate tuition", "per_credit"), ("Technology fee", "technology_per_credit")]:
        rate = data["tuition"].get(key)
        amount = (Decimal(rate) * credits).quantize(Decimal("0.01")) if rate is not None else None
        rows.append({"description": label, "credits": credits, "rate": rate,
                     "amount": str(amount) if amount is not None else None})
    total = sum((Decimal(r["amount"]) for r in rows), Decimal("0.00")) if all(r["amount"] is not None for r in rows) else None
    return rows, total


def font(size, bold=False):
    names = (["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
             if bold else ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


class Canvas:
    def __init__(self, size):
        self.image = Image.new("RGB", size, "white")
        self.draw = ImageDraw.Draw(self.image)
        self.texts = []

    def box(self, xy, fill):
        self.draw.rectangle(xy, fill=fill)

    def text(self, value, xy, size=26, color=INK, bold=False, align="left"):
        value = str(value)
        if not value.isascii():
            raise ValueError("Document text must be English ASCII.")
        x, y, w, h = xy
        for point in range(size, 11, -1):
            face = font(point, bold)
            lines = []
            for paragraph in value.split("\n"):
                line = ""
                for word in paragraph.split():
                    candidate = (line + " " + word).strip()
                    if self.draw.textlength(candidate, font=face) <= w:
                        line = candidate
                    else:
                        if line:
                            lines.append(line)
                        line = word
                        # Preserve unusually long names instead of clipping or truncating them.
                        while self.draw.textlength(line, font=face) > w:
                            split = len(line) - 1
                            while split > 0 and self.draw.textlength(line[:split], font=face) > w:
                                split -= 1
                            if not split:
                                break
                            lines.append(line[:split])
                            line = line[split:]
                lines.append(line)
            step = point + 8
            if len(lines) * step <= h and all(self.draw.textlength(line, font=face) <= w for line in lines):
                break
        else:
            raise ValueError(f"Text does not fit its reserved area: {value[:60]}")
        for i, line in enumerate(lines):
            length = self.draw.textlength(line, font=face)
            left = x if align == "left" else x + w - length
            self.draw.text((left, y + i * step), line, font=face, fill=color, anchor="lt")
        self.texts.append({"text": value, "box": [x, y, w, h], "font_size": point})

    def label(self, label, value, x, y, width=420):
        self.text(label.upper(), (x, y, width, 28), 18, MUTED, True)
        self.text(value, (x, y + 34, width, 70), 28, INK, True)

    def image_at(self, asset, box):
        self.image.paste(ImageOps.fit(asset, (box[2], box[3])), (box[0], box[1]))

    def disclaimer(self, kind, y):
        self.box((0, y, self.image.width, y + DISCLAIMER_HEIGHT), RED)


def heading(c, title, subtitle, banner=None):
    width = c.image.width
    c.box((0, 0, width, 12), RED)
    c.text("UMGC / INDEPENDENT DESIGN PROTOTYPE", (60, 42, width - 120, 38), 22, RED, True)
    c.text(title, (60, 99, width - 120, 82), 58, INK, True)
    c.text("University of Maryland Global Campus", (60, 184, width - 120, 42), 28)
    c.text(subtitle, (60, 237, width - 120, 45), 23, MUTED)
    if banner:
        c.image_at(banner, (60, 300, width - 120, 100))


def render_schedule(profile, data, assets):
    c = Canvas(SIZES["schedule"])
    session = data["session"]
    heading(c, "Course Schedule", f"{session['term']}  |  {session['name']}", assets["banner"])
    c.label("Fictional student", profile["full_name"], 60, 426, 600)
    c.label("Prototype ID", profile["student_id"], 770, 426, 450)
    c.text(f"{session['start']} to {session['end']}  |  United States  |  Proposed online study",
           (60, 538, 1480, 45), 23, MUTED)
    c.box((60, 608, 1540, 665), INK)
    for text, x, w in [("COURSE", 80, 220), ("TITLE", 320, 650), ("CREDITS", 1010, 150), ("FORMAT", 1220, 300)]:
        c.text(text, (x, 627, w, 32), 20, "white", True)
    for i, course in enumerate(data["courses"]):
        y = 665 + i * 105
        c.box((60, y, 1540, y + 104), LIGHT if i % 2 == 0 else "#F9FAFB")
        c.text(course["code"], (80, y + 25, 220, 65), 29, INK, True)
        c.text(course["title"], (320, y + 20, 650, 75), 27)
        c.text(course["credits"], (1010, y + 25, 150, 65), 29)
        c.text("Online\nAsynchronous*", (1220, y + 20, 300, 75), 23)
    c.text("* Proposed format only. Section availability and prerequisites have not been verified.",
           (60, 896, 1480, 40), 21, MUTED)
    c.text("Fictional course selection. Not a registration record. Public-source check: " + data["verified_on"],
           (60, 944, 1480, 40), 21, MUTED)
    c.disclaimer("schedule", c.image.height - DISCLAIMER_HEIGHT)
    return c


def render_card(profile, data, assets):
    c = Canvas(SIZES["student_card"])
    session = data["session"]
    heading(c, "Student Card", "DESIGN PROTOTYPE / FICTIONAL PERSON")
    c.image_at(assets["portrait"], (60, 327, 360, 390))
    c.text("FICTIONAL PERSON / NOT A REAL STUDENT", (60, 736, 360, 55), 18, MUTED, True)
    c.label("Name", profile["full_name"], 480, 330, 1060)
    c.label("Prototype ID", profile["student_id"], 480, 455, 460)
    c.label("Country", profile["country"], 1020, 455, 500)
    c.label("Date of birth", profile["date_of_birth"], 480, 580, 460)
    c.label("Age at session start", str(age_on(profile["date_of_birth"], session["start"])), 1020, 580, 500)
    c.text(data["program"] + " / Undergraduate", (480, 705, 1060, 52), 28, INK, True)
    c.box((60, 810, 1540, 897), LIGHT)
    c.text(f"PROTOTYPE VALID FROM {session['start']} THROUGH {session['end']}",
           (80, 829, 1440, 43), 27, INK, True)
    c.disclaimer("student_card", c.image.height - DISCLAIMER_HEIGHT)
    return c


def render_receipt(profile, data, assets):
    c = Canvas(SIZES["receipt"])
    session = data["session"]
    heading(c, "Tuition Receipt", "DESIGN PROTOTYPE / NO PAYMENT RECORDED", assets["banner"])
    c.label("Fictional student", profile["full_name"], 60, 436, 640)
    c.label("Prototype ID", profile["student_id"], 760, 436, 455)
    c.label("Academic term", session["term"], 60, 558, 500)
    c.label("Session dates", f"{session['start']} to {session['end']}", 640, 558, 575)
    c.text("COST BASIS / OUT-OF-STATE UNDERGRADUATE", (60, 700, 1155, 45), 24, RED, True)
    credits = sum(course["credits"] for course in data["courses"])
    c.text(f"{credits} proposed credits. Civilian rate; no military or corporate discount assumed.",
           (60, 757, 1155, 75), 25, MUTED)
    c.box((60, 858, 1215, 918), INK)
    for text, x, w in [("DESCRIPTION", 80, 550), ("CREDITS", 635, 140), ("RATE", 800, 140), ("AMOUNT", 975, 220)]:
        c.text(text, (x, 879, w, 31), 20, "white", True)
    rows, total = fee_rows(data)
    for i, row in enumerate(rows):
        y = 918 + 102 * i
        c.box((60, y, 1215, y + 101), LIGHT if i % 2 == 0 else "#F9FAFB")
        c.text(row["description"], (80, y + 31, 530, 60), 25)
        c.text(row["credits"], (635, y + 31, 140, 60), 25)
        c.text(money(row["rate"]) if row["rate"] is not None else "", (800, y + 31, 155, 60), 25)
        c.text(money(row["amount"]) if row["amount"] is not None else "", (975, y + 31, 220, 60), 25, align="right")
    c.box((60, 1163, 1215, 1255), INK)
    c.text("ESTIMATED TOTAL (USD)", (80, 1190, 780, 50), 28, "white", True)
    c.text(money(total) if total is not None else "", (890, 1183, 305, 60), 38, "white", True, "right")
    c.text("No payment, transaction or balance settlement is represented by this design.",
           (60, 1300, 1155, 84), 25, RED, True)
    c.text("Public tuition rates checked " + data["verified_on"] + ". Rates may change.\n"
           "Other fees, materials and discounts are not included. See sources.json for evidence and assumptions.",
           (60, 1414, 1155, 125), 23, MUTED)
    c.disclaimer("receipt", c.image.height - DISCLAIMER_HEIGHT)
    return c


def local_asset(kind):
    # Explicit offline QA artwork; never presented as a successful AI result.
    image = Image.new("RGB", (1024, 1024), LIGHT)
    draw = ImageDraw.Draw(image)
    if kind == "portrait":
        draw.ellipse((340, 180, 684, 524), fill="#B9BEC7")
        draw.rounded_rectangle((210, 575, 814, 1050), radius=155, fill=INK)
        draw.rectangle((210, 890, 814, 950), fill=RED)
    else:
        draw.rectangle((0, 450, 1024, 730), fill=INK)
        draw.rectangle((720, 0, 865, 1024), fill=RED)
        draw.rectangle((890, 0, 934, 1024), fill=GOLD)
    return image


def asset_prompts(profile, session):
    age = age_on(profile["date_of_birth"], session["start"])
    return {
        "portrait": f"Photorealistic studio portrait of an entirely fictional {age}-year-old adult university student in the United States. "
        "Shoulders and head centered, contemporary casual clothing, pale gray background. "
        "Natural skin texture, realistic facial proportions, soft daylight, sharp eyes, front facing. "
        "Invent a new person, not a real student or recognizable person. No text, letters, logos or numbers. "
        f"Fictional character variation reference: {profile['student_id']}. For a visibly unofficial design prototype only.",
        "banner": "Clean editorial photograph of blank notebooks and a closed unbranded laptop on a white desk. "
        "Overhead view, charcoal and muted crimson accents. Bright, sharp natural lighting. "
        "Objects across the center horizontal band. No people, text, letters, logos or documents.",
    }


def prompts_for_presentation(profile, session, presentation):
    prompts = asset_prompts(profile, session)
    if presentation == "code_v2":
        return {"portrait": prompts["portrait"]}
    return prompts


def phone_photograph(document, seed, background=None):
    """Photograph-style staging, preserving the complete unofficial document."""
    rng = random.Random(seed)
    width, height = document.size
    texture = Image.new("RGB", (192, 192))
    texture.putdata([
        (151 + n, 158 + n, 155 + n)
        for n in (rng.randrange(-7, 8) for _ in range(192 * 192))
    ])
    desk = texture.resize(document.size, Image.Resampling.BICUBIC).convert("RGBA")
    if background is not None:
        desk = ImageOps.fit(background, document.size, Image.Resampling.LANCZOS).convert("RGBA")
    lighting = Image.new("RGB", (128, 128))
    lighting.putdata([
        (v, v, max(0, v - 2))
        for y in range(128) for x in range(128)
        for v in [int(253 - 12 * x / 127 - 5 * y / 127) + rng.randrange(-1, 2)]
    ])
    paper = ImageChops.multiply(document.convert("RGB"), lighting.resize(document.size))
    paper = ImageOps.contain(paper, (int(width * .79), int(height * .80)), Image.Resampling.LANCZOS)
    paper = paper.convert("RGBA").rotate(rng.choice([-2.2, 1.8]), Image.Resampling.BICUBIC, expand=True)
    left, top = (width - paper.width) // 2, (height - paper.height) // 2
    layer = Image.new("RGBA", document.size)
    layer.alpha_composite(paper, (left, top))
    if background is not None:
        layer = layer.transform(document.size, Image.Transform.PERSPECTIVE,
                                (1, .018, -width * .009, .009, 1, -height * .004,
                                 rng.uniform(-.018, .018) / width, .014 / height),
                                Image.Resampling.BICUBIC)
    mask = Image.new("L", document.size)
    mask.paste(layer.getchannel("A"), (10, 16))
    mask = mask.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * .32))
    shadow = Image.new("RGBA", document.size, (23, 29, 27, 0))
    shadow.putalpha(mask)
    desk = Image.alpha_composite(desk, shadow)
    desk = Image.alpha_composite(desk, layer)
    return desk.convert("RGB")


def save_image(image, path):
    temp = path.with_suffix(".tmp.png")
    image.save(temp, format="PNG")
    temp.replace(path)


def verified_existing(batch, record):
    path = batch / record["file"]
    if path.parent.resolve() != batch.resolve() or not path.exists() or digest(path) != record["sha256"]:
        raise ValueError("A completed batch artifact is missing or changed; create a new batch.")
    return path


@contextmanager
def batch_lock(batch):
    lock = batch / ".run.lock"
    try:
        handle = lock.open("x")
    except FileExistsError:
        raise ValueError("Batch is already running; do not start concurrent resume requests.") from None
    try:
        handle.close()
        yield
    finally:
        lock.unlink()


def generate_document_set(*, profile_path="profile.json", resource_zip=None, out_dir="outputs",
                          base_name="umgc_doc", seed=None, new_profile=False, resume=None,
                          render_mode="ai", base_url="http://localhost:3000/v1", api_key=None,
                          model="gpt-image-2", timeout=300, ai_generator=None, output_size=None,
                          on_batch=None):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", base_name):
        raise ValueError("Base name must use 1-80 ASCII letters, digits, underscores or hyphens.")
    if output_size and (min(output_size) < 600 or max(output_size) > 6000):
        raise ValueError("Document output bounds must be between 600 and 6000 pixels.")
    if render_mode not in ("ai", "local"):
        raise ValueError("Render mode must be ai or local.")
    if resume:
        if new_profile:
            raise ValueError("Cannot create a new profile when resuming a batch.")
        batch = Path(resume).resolve()
        job = read_json(batch / "job.json")
        if job.get("schema_version") != 1:
            raise ValueError("Unsupported batch version.")
        inputs = read_json(verified_existing(batch, job["inputs"]))
        for record in job.get("supporting", []):
            verified_existing(batch, record)
        profile, data = inputs["profile"], inputs["data"]
        render_mode, model, base_name = inputs["render_mode"], inputs["model"], inputs["base_name"]
        output_size = inputs["output_size"]
        validate_profile(profile, data["session"])
    else:
        data = read_json(SNAPSHOT)
        imported = inspect_resource_zip(resource_zip)
        profile, path = get_profile(profile_path, data["session"], seed, new_profile)
        batch = Path(out_dir).resolve() / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
        batch.mkdir(parents=True, exist_ok=False)
        presentation = DEFAULT_PRESENTATION
        inputs = {"profile": profile, "profile_path": str(path), "data": data,
                  "render_mode": render_mode, "model": model, "base_name": base_name,
                  "output_size": output_size, "prompts": prompts_for_presentation(profile, data["session"], presentation),
                  "presentation": presentation, "layout_seed": str(seed) if seed is not None else uuid.uuid4().hex}
        scene = random.Random(inputs["layout_seed"]).choice([
            "a pale ash wood study desk, a capped pen at the extreme upper edge",
            "a matte gray laminate library table, a closed notebook at the extreme left edge",
            "a white painted desk with subtle wear, a pencil near the far upper right corner"])
        if presentation != "code_v2":
            inputs["prompts"]["banner"] = (
                "Natural smartphone photograph looking almost straight down at " + scene + ". "
                "A completely empty clear central tabletop occupying 90 percent of the image. "
                "No paper, no document, no text, no letters, no laptop, no people. "
                "Soft window daylight, realistic material grain, subtle uneven illumination. "
                "Casual handheld framing, not a commercial product render. All objects only at the outer edge.")
        write_json(batch / "inputs.json", inputs)
        write_json(batch / "profile.json", profile)
        write_json(batch / "sources.json", {"verified_public_data": data, "supplied_resources": imported,
                   "field_provenance": {"name_birth_country_id": "locally generated fictional profile",
                       "term_dates": "calendar", "course_titles_credits": "courses",
                       "rates": "tuition", "selection_format_card_dates": "prototype assumptions",
                       "amounts": "Decimal arithmetic, not an actual payment"}})
        job = {"schema_version": 1, "status": "created", "render_mode": render_mode, "model": model,
               "inputs": {"file": "inputs.json", "sha256": digest(batch / "inputs.json")},
               "supporting": [{"file": name, "sha256": digest(batch / name)} for name in ("profile.json", "sources.json")],
               "assets": {}, "outputs": {}}
        write_json(batch / "job.json", job)
    if on_batch is not None:
        on_batch(batch)
    with batch_lock(batch):
        # Re-read state under the lock so simultaneous resume attempts cannot overwrite progress.
        job = read_json(batch / "job.json")
        return run_batch(batch, job, inputs, base_url, api_key, timeout, ai_generator)


def run_batch(batch, job, inputs, base_url, api_key, timeout, ai_generator):
    profile, data = inputs["profile"], inputs["data"]
    render_mode, model, base_name = inputs["render_mode"], inputs["model"], inputs["base_name"]
    output_size = inputs["output_size"]
    try:
        assets = {}
        generator = ai_generator or make_ai_image
        job["status"] = "running"
        job.pop("error", None)
        write_json(batch / "job.json", job)
        for kind, prompt in inputs["prompts"].items():
            if kind in job["assets"]:
                path = verified_existing(batch, job["assets"][kind])
                with Image.open(path) as image:
                    assets[kind] = image.convert("RGB")
            else:
                assets[kind] = local_asset(kind) if render_mode == "local" else generator(
                    prompt, base_url, api_key, model, "1024x1024", timeout)
                path = batch / f"asset_{kind}.png"
                save_image(assets[kind], path)
                job["assets"][kind] = {"file": path.name, "sha256": digest(path)}
                write_json(batch / "job.json", job)
        for kind, renderer in [("schedule", render_schedule), ("student_card", render_card), ("receipt", render_receipt)]:
            if kind in job["outputs"]:
                verified_existing(batch, job["outputs"][kind])
                continue
            if inputs.get("presentation") == "code_v2":
                import document_layouts
                canvas = document_layouts.render_code_v2(kind, profile, data, assets, inputs["layout_seed"])
            elif inputs.get("presentation") in ("desk_photo_v2", "electronic_v1"):
                import document_layouts
                canvas = document_layouts.render_variant(kind, profile, data, assets, inputs["layout_seed"])
            else:
                canvas = renderer(profile, data, assets)
            presentation = "flat"
            if kind in ("schedule", "receipt") and inputs.get("presentation") == "phone_photo_v1":
                canvas.image = phone_photograph(canvas.image, profile["student_id"] + kind)
                presentation = "phone_photo_v1"
            elif kind in ("schedule", "receipt") and inputs.get("presentation") == "desk_photo_v2":
                canvas.image = phone_photograph(canvas.image, inputs["layout_seed"] + kind, assets["banner"])
                presentation = "desk_photo_v2"
            elif inputs.get("presentation") in ("electronic_v1", "code_v2"):
                presentation = inputs.get("presentation")
            if output_size:
                canvas.image = ImageOps.contain(canvas.image, tuple(output_size), Image.Resampling.LANCZOS)
            path = batch / f"{base_name}_{kind}.png"
            save_image(canvas.image, path)
            job["outputs"][kind] = {"file": path.name, "sha256": digest(path),
                                   "size": list(canvas.image.size), "rendered_text": canvas.texts,
                                   "presentation": presentation, "text_coordinate_space": "flat_document"}
            write_json(batch / "job.json", job)
        job["status"] = "complete"
        write_json(batch / "job.json", job)
    except Exception as exc:
        error = str(exc).replace(api_key, "[REDACTED]") if api_key else str(exc)
        job["status"], job["error"] = "failed", error
        write_json(batch / "job.json", job)
        raise RuntimeError(f"Batch failed: {error}\nResume with --mode documents --resume \"{batch}\"") from None
    return batch, [batch / job["outputs"][kind]["file"] for kind in SIZES]
