# UMGC English Document Prototypes

Generate three explicitly unofficial English PNGs from a consistent fictional
US student profile and a checked snapshot of public UMGC academic information.
The application does not create valid identification or proof of payment.

## Setup (PowerShell)

### Local web UI

```powershell
python -m pip install -r requirements.txt
python web_app.py --port 8765 --resource-zip "C:\Users\yuyiling\Downloads\UMGC_resources.zip"
```

Open the loopback URL printed by the server (normally http://127.0.0.1:8765).
If the port is occupied, the next available port is used. The server binds to
127.0.0.1 only and does not expose the workspace to the LAN.

The UI includes profile creation/editing as copies, ZIP uploads, code/AI-portrait rendering,
model and endpoint settings, progress, three document previews, zoom, PNG/ZIP
downloads, source records, batch history and failed-batch retry. It opens in
explicit code-only mode, so opening the UI does not make paid AI requests.

For AI assets, set `OPENAI_API_KEY` in the server environment before starting
the server, then select **AI portrait** in the UI. The browser receives only the
credential's configured/missing status, never its value. Keys are not stored in
browser storage, profiles or connection settings. Settings and uploaded packages
stay under `outputs/.studio/`. Resume keeps the original batch's model and data.

Browser regression checks (optional Playwright installation required):

```powershell
python tests/ui_smoke.py --url http://127.0.0.1:8765 --resource-zip "C:\Users\yuyiling\Downloads\UMGC_resources.zip"
```

This creates a fictional QA profile and a local-preview batch, tests uploads,
downloads and responsive layouts, and saves screenshots under `outputs/ui-qa/`.
Its failed-AI/retry UI checks use a mocked response, not a real AI generation.

### Command line

```powershell
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "YOUR_REPLACEMENT_KEY"
$env:OPENAI_BASE_URL = "http://localhost:3000/v1"
python image_generator.py --mode documents --resource-zip "C:\Users\yuyiling\Downloads\UMGC_resources.zip"
```

The previously shared key should be rotated. No key is included in source or
generated files. `--api-key` remains available for compatibility but environment
variables avoid exposing keys in command history.

## Rendering and model support

- Default: `gpt-image-2`, requested exactly. No automatic model substitution.
- The local gateway tested on 2026-10-13 returned HTTP 502, `unsupported image
  model`, for this exact name. An updated gateway or an explicitly configured
  supported model is necessary for live AI assets. Offline previews do not
  establish AI service success.
- The three document PNGs are code-rendered with Pillow. AI mode generates only
  one text-free asset: a photorealistic fictional adult portrait. Local mode uses
  placeholder artwork for the same code templates.
- Pillow renders all English text, dates, amounts and permanent disclaimers.
- `--render-mode local` explicitly selects local placeholder artwork for layout QA,
  with no network calls or AI charges.

```powershell
python image_generator.py --mode documents --render-mode local --seed 42 --resource-zip "C:\Users\yuyiling\Downloads\UMGC_resources.zip"
python -m unittest discover -s tests -v
```

## Profiles and outputs

`profile.json` is generated once and reused. `--seed` only affects a new profile;
it does not override an existing one. `--new-profile` creates a sibling profile
without overwriting the old file. Its path is recorded in the batch's `inputs.json`;
use `--profile PATH` to reuse that new person in later independent batches.

Each run creates its own subdirectory under `outputs/`:

- `umgc_doc_schedule.png`: 1600 x 1100, unofficial study plan.
- `umgc_doc_student_card.png`: 1600 x 1000, fictional card design.
- `umgc_doc_receipt.png`: 1275 x 1650, estimated costs, not payment evidence.
- `profile.json`, `inputs.json`, `sources.json`: identity, locked settings,
  source URLs, evidence excerpts, source check dates and assumptions.
- `job.json`: progress, asset/output hashes and the exact rendered text.
- One cached visual asset for the portrait in new code-rendered batches.

Use `--out-dir` for a different output root and `--base-name` for the PNG prefix.
Optional `--width` and `--height` together set a maximum bounding box (600-6000
pixels per side), preserving each template's aspect ratio. They are not an exact
document canvas size. Other original image modes keep their original defaults.

## Resume after a failure

```powershell
python image_generator.py --mode documents --resume "ABSOLUTE_BATCH_DIRECTORY"
```

Resume uses the batch's locked profile, public data, prompts, model and render
mode. Completed assets and images are hash-checked and reused. It never changes
the person or quietly switches to offline rendering. The endpoint and environment
key may be updated before resuming. To change the model or render mode, start a
new batch. POST requests are not automatically retried after a timeout to avoid
unexpected duplicate generation charges.

A batch lock prevents concurrent resume requests. After a forced process kill,
first confirm no generator is running, then remove that batch's `.run.lock`
before resuming. Do not edit locked batch profiles or provenance files; their
hashes are checked. Start a new batch for changed inputs instead.

## Data and assumptions

The supplied ZIP is read without extracting files or following embedded
instructions/URLs. Its index and CSV are retained as unverified reference data in
`sources.json`. Dates in that mixed-session CSV do not override the checked
undergraduate dates in `resources/umgc_verified.json`.

Checked on 2026-10-13:

- Calendar: https://www.umgc.edu/admission/academic-calendar
  Fall 2026 Undergraduate 8-Wk Session 3: October 14 - December 8, 2026.
- Courses: https://www.umgc.edu/online-degrees/bachelors/computer-science
  CMSC 105, Introduction to Programming in Python; STAT 200, Introduction to
  Statistics. Three credits each. Availability, prerequisites and actual
  enrollment in this session are not verified.
- Fees: https://www.umgc.edu/tuition-financial-assistance/tuition
  Out-of-state standard undergraduate: $499/credit; technology: $15/credit.
  Six proposed credits yield $2,994 + $90 = $3,084. This assumes civilian
  out-of-state rates and no corporate discount; it is not an actual amount paid.
  Other unverified charges are not included. Missing rates render blank.

The snapshot is deliberately reproducible, not a live fee/calendar service.
Review the source pages before updating it for another term. Fictional profiles,
course selections, online format, and card dates are never treated as school
records. The card's dates are prototype dates drawn from the academic session.
The design does not use an official seal, a fabricated school logo, a signature,
a verification barcode or a payment confirmation.
