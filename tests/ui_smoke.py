"""Run against an already-started local studio; writes screenshots to outputs/ui-qa."""

import argparse
import json
import re
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--resource-zip", required=True)
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / "outputs" / "ui-qa"
    output.mkdir(parents=True, exist_ok=True)
    errors = []
    report = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until="networkidle")
        expect(page.locator("#document-image")).to_be_visible()
        expect(page.locator("#connection-alert")).to_be_hidden()
        assert page.locator("svg.lucide").count() > 20

        page.get_by_role("tab", name="Student card").click()
        page.get_by_role("button", name="Zoom in", exact=True).click()
        expect(page.locator("#zoom-level")).to_have_text("125%")
        page.get_by_role("button", name="Fit document", exact=True).click()
        expect(page.locator("#zoom-level")).to_have_text("100%")
        page.get_by_role("button", name="Expand preview", exact=True).click()
        expect(page.locator("#image-dialog")).to_be_visible()
        page.keyboard.press("Escape")
        page.get_by_role("button", name="Source notes", exact=True).click()
        expect(page.locator("#sources-dialog")).to_be_visible()
        expect(page.locator("#sources-content a")).to_have_count(3)
        page.keyboard.press("Escape")

        page.get_by_role("button", name="Edit a copy of this profile").click()
        page.locator("#edit-name").fill("Avery Parker")
        page.locator("#edit-dob").fill("2015-05-17")
        page.get_by_role("button", name="Save profile", exact=True).click()
        expect(page.locator("#profile-error")).to_contain_text("18-24")
        page.locator("#edit-dob").fill("2004-05-17")
        page.get_by_role("button", name="Save profile", exact=True).click()
        expect(page.locator("#profile-dialog")).to_be_hidden()
        expect(page.locator("#profile-name")).to_have_text("Avery Parker")
        page.locator("#resource-file").set_input_files(args.resource_zip)
        expect(page.locator("#toast")).to_have_text("Resource package uploaded.")

        page.locator('input[name="render-mode"][value="ai"]').check()
        if page.locator("#key-status").inner_text() == "No API key":
            expect(page.locator("#generate")).to_be_disabled()
            expect(page.locator("#generation-warning")).to_be_visible()
        page.locator('input[name="render-mode"][value="local"]').check()
        page.get_by_role("button", name=re.compile("(Generate|Regenerate) 3 images")).click()
        expect(page.locator("#toast")).to_contain_text(re.compile("(Three images are ready|saved to history)"), timeout=30000)
        expect(page.locator("#download-set")).to_have_attribute("aria-disabled", "false")
        expect(page.locator(".thumbnail img")).to_have_count(3)
        batch_id = page.locator("#batch-reference").inner_text().replace("Batch ", "")
        batch = context.request.get(f"{args.url}/api/batches/{batch_id}").json()
        assert batch["profile"]["full_name"] != "Avery Parker"
        assert batch["status"] == "complete"
        assert batch["render_mode"] == "local"

        with page.expect_download() as pending:
            page.locator("#download-set").click()
        pending.value.save_as(output / "downloaded-set.zip")
        with zipfile.ZipFile(output / "downloaded-set.zip") as archive:
            assert len(archive.namelist()) == 5
        with page.expect_download() as pending:
            page.locator("#download-image").click()
        pending.value.save_as(output / "downloaded-card.png")
        report["batch_id"] = batch_id
        report["download_entries"] = 5

        page.get_by_role("button", name="Regenerate 3 images", exact=True).click()
        expect(page.locator("#toast")).to_have_text("New three-image set saved to history.", timeout=30000)
        expect(page.locator("#batch-reference")).to_contain_text("Batch ")
        regenerated_id = page.locator("#batch-reference").inner_text().replace("Batch ", "")
        assert regenerated_id != batch_id
        assert regenerated_id != "No batch selected"
        report["regenerated_batch_id"] = regenerated_id
        regenerated = context.request.get(f"{args.url}/api/batches/{regenerated_id}").json()
        assert regenerated["profile"]["full_name"] != batch["profile"]["full_name"]
        assert regenerated["profile"]["student_id"] != batch["profile"]["student_id"]
        expect(page.locator("#profile-name")).to_have_text(regenerated["profile"]["full_name"])

        page.get_by_role("tab", name="Course schedule").click()
        expect(page.locator("#document-image")).to_be_visible()
        expect(page.locator("#toast")).to_be_hidden(timeout=10000)
        page.screenshot(path=str(output / "desktop.png"), full_page=True)
        report["desktop_overflow"] = page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.get_by_role("button", name="Batch history").click()
        expect(page.locator("#history-view")).to_be_visible()
        expect(page.locator("#history-body tr").first).to_contain_text(regenerated["profile"]["full_name"])
        assert page.locator("#history-body tr").count() >= 2
        page.locator("#history-filter").select_option("complete")
        page.screenshot(path=str(output / "history.png"), full_page=True)
        page.get_by_role("button", name=f"Open batch {batch_id}").click()

        page.set_viewport_size({"width": 390, "height": 844})
        page.get_by_role("tab", name="Tuition receipt").click()
        expect(page.locator("#document-image")).to_be_visible()
        page.screenshot(path=str(output / "mobile.png"), full_page=True)
        report["mobile_overflow"] = page.evaluate("document.documentElement.scrollWidth > innerWidth")
        report["mobile_button_overflow"] = page.locator("button").evaluate_all(
            "buttons => buttons.filter(b => b.getClientRects().length && b.scrollWidth > b.clientWidth + 2).map(b => b.textContent.trim())")
        for width in [320, 768, 1024, 1920]:
            page.set_viewport_size({"width": width, "height": 900})
            page.wait_for_timeout(100)
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), width
        assert not report["desktop_overflow"]
        assert not report["mobile_overflow"]
        assert not report["mobile_button_overflow"], report["mobile_button_overflow"]

        # UI failure/retry states use a mocked transport, not a paid AI request.
        page.set_viewport_size({"width": 1440, "height": 1000})
        failure = {**batch, "status": "failed", "error": "HTTP 502: unsupported image model gpt-image-2"}
        page.route("**/api/tasks", lambda route: route.fulfill(json={"id": "ui-failure", "status": "queued"}))
        page.route("**/api/tasks/ui-failure", lambda route: route.fulfill(json={"id": "ui-failure", "status": "failed", "error": failure["error"], "batch": failure}))
        page.get_by_role("button", name=re.compile("(Generate|Regenerate) 3 images")).click()
        expect(page.locator("#batch-message")).to_be_visible()
        expect(page.locator("#batch-message-detail")).to_contain_text("unsupported image model")
        page.screenshot(path=str(output / "failure.png"), full_page=True)
        page.unroute("**/api/tasks/ui-failure")
        page.route("**/api/tasks/ui-failure", lambda route: route.fulfill(json={"id": "ui-failure", "status": "complete", "batch": batch}))
        page.get_by_role("button", name="Retry batch", exact=True).click()
        expect(page.locator("#toast")).to_have_text("Three images are ready.")
        report["mocked_failure_retry"] = "passed"
        assert not errors, errors
        report["browser_errors"] = errors
        context.close()
        browser.close()
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
