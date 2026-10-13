# UMGC English Document Prototype Generator

## Scope
Implement the approved design: three clearly unofficial English images, a
persistent fictional US student profile, verified public academic data,
AI-only visual assets, and deterministic Pillow text rendering.

## Phases
- [x] Inspect existing generator and supplied ZIP.
- [x] Verify undergraduate calendar against the official page.
- [x] Verify course and tuition facts; record provenance.
- [x] Implement profile, sources, AI assets, layouts, and batch resume.
- [x] Add focused automated tests and run local render verification.
- [x] Attempt the requested model against the configured service; report results accurately.

## External blocker
The configured local gateway rejects gpt-image-2.5 with HTTP 502. Real AI asset
generation remains unverified. Offline previews and mocked API tests are separate.

## Decisions
- Keep fictional identity and non-official labels on all deliverables.
- User explicitly switched to gpt-image-2 on 2026-10-13; request it exactly without automatic fallback.
- Preserve existing outputs and unrelated local changes.
- Credentials must not be stored in source, profiles, manifests, or logs.

## Local Web UI
- [x] Switch current output presentation from phone-photo staging to clean electronic documents and regenerate a fresh set.
- [x] Replace noise backgrounds with AI desk scenes and batch-specific document layouts; generate and inspect a fresh live batch.
- [x] Add photograph-style schedule and receipt staging; preserve disclaimers and historical batches. 39 tests passed.
- [x] Switch defaults to gpt-image-2 and verify a live photorealistic portrait and document batch.
- [x] Fix fresh-person batches and photorealistic fictional portraits; verify tests and runtime. Live AI remains unavailable without a configured key and supported model.
- [x] Inspect generator interfaces, existing previews and available dependencies.
- [x] Add a loopback-only web backend with uploads, profiles, asynchronous jobs and downloads.
- [x] Build the document workspace, preview tools, settings and batch history.
- [x] Test API security and complete local generation through the browser.
- [x] Verify desktop/mobile screenshots and start the local server.

## Code-Rendered Documents V2
- [x] Add a deterministic code-only document template for the three PNGs.
- [x] Limit AI mode to optional portrait generation; avoid generating unused full-document or desk assets for code output.
- [x] Update UI copy and progress to describe code-rendered documents accurately.
- [x] Extend tests for code_v2 output, asset counts, text bounds and retry behavior.
- [x] Generate and inspect a fresh batch; restart the local service if tests pass.
