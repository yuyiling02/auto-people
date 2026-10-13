# Progress

## 2026-10-13
- Inspected current files without modifying user outputs.
- User approved a fictional consistent identity with conspicuous English disclaimers.
- Began official course/tuition verification and implementation.
- Implemented persistent fictional profiles, source snapshots, secure API client,
  English Pillow layouts, independent output batches and resume support.
- First 21 automated tests passed; generated and visually inspected all three
  local preview PNGs. No overlap, clipped text or Chinese text observed.
- Added tests for long unbroken names, source/profile integrity and concurrent resume.
- All 24 tests passed after the additional checks. Syntax and embedded-key scans passed.
- Final local preview batch: outputs/20261012T172446Z-001211bf.
- Added UTF-8 console output so Chinese Windows paths are readable through pipes.

## Web UI
- Added a local Flask backend; credentials remain server-side. Added same-origin,
  Host and CSRF checks, validated ZIP uploads and asynchronous generation.
- Built a responsive document workspace with three previews, zoom/full-screen,
  profiles, resource packages, settings, downloads, sources and batch history.
- Added backend end-to-end and security tests; browser verification is next.
- Fixed a Windows atomic-file read/write race exposed by frequent progress polling.
- All 34 unit/integration tests pass. Browser tests passed for ZIP upload, profile
  validation, three-image local generation, PNG/ZIP downloads, zoom and history.
- Mocked failed-model/retry UI tests passed; this is not a live AI success claim.
- Inspected desktop/mobile screenshots; 320, 390, 768, 1024, 1440 and 1920 pixel
  layouts have no page overflow. Browser reported no JavaScript errors.
- Server running on http://127.0.0.1:8765, loopback only. UI starts in local-preview
  mode; OPENAI_API_KEY is currently not configured in the server environment.
- Fresh-person regeneration and photorealistic fictional portrait prompt implemented. 38 tests pass; browser smoke confirms distinct names/IDs across batches, synchronized profile panel, retained history, retry and no responsive overflow. AI portrait integration tested with a mock, not a live model.
- Restarted stale UI process; current service PID 59524 on port 8765. First browser run caught stale backend; rerun after restart passed.
- User switched to gpt-image-2. The service was restarted with the server-only key
  and a live batch completed: model gpt-image-2, profile Taylor James Bennett,
  batch 20261012T185637Z-c0819dea. Portrait asset and profile image saved.
- Added paper lighting, desk texture, rotated full-page framing and soft shadows for
  schedule/receipt outputs. Student cards unchanged; non-official labels preserved.
- 39 tests passed. Style revision 20261012T191212Z-dcec1a7b reuses existing AI assets
  with provenance recorded; original batch retained and no new paid request made.
- Live batch 20261012T191838Z-a0f579b7 uses gpt-image-2 desk scene, fresh profile,
  varied layout, and phone-photo composition; schedule/receipt inspected successfully.
- User requested formal electronic documents. New electronic_v1 batch
  20261012T195104Z-31dc8ca6 generated with clean digital layout, no desk/camera effects,
  fresh profile, and course time blocks; 41 tests pass.
- Added code_v2 templates for the schedule, student card and tuition estimate.
  The three PNGs are now drawn by Pillow tables/cards/fields; AI mode only requests
  a portrait asset and local mode uses the placeholder portrait.
- Updated web batch metadata and progress display for dynamic asset counts. UI mode
  labels now read Code only and AI portrait.
- Updated retry tests for one portrait asset and code-rendered resume behavior.
  `python -m unittest discover -s tests` passed: 42 tests.
- Generated and inspected code_v2 local preview batch
  outputs/20261012T222221Z-030b398a. Service restarted on port 8765 with PID 10712;
  `/api/batches/20261012T222221Z-030b398a` reports presentation=code_v2,
  assets_total=1 and outputs_done=3.
