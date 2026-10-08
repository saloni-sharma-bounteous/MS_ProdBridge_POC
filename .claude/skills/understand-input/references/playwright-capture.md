# Live capture with Playwright

## Install (once)
```
pip install playwright
playwright install chromium
python3 scripts/ui_capture.py --check      # prints "Playwright and Chromium are ready."
```
Behind a corporate proxy or mirror, follow the organisation's instructions for downloading browsers. Without Playwright, use the static snapshot for HTML files, or screenshots.

## Runs
```
python3 scripts/ui_capture.py --input prototype/ --out handoff/ui            # a folder or one .html file, served locally
python3 scripts/ui_capture.py --url https://pilot.example.test/ --out handoff/ui --max-pages 25
python3 scripts/ui_capture.py --input prototype/ --out handoff/ui --states states.json
```
`--click-safe` also presses buttons whose text looks harmless (open, view, filter, next) and records where they lead.

## States
Screens that only appear after sign-in or after choosing a role need a scripted state. Write `states.json` with synthetic values:
```json
[{"name": "employee", "steps": [
   {"action": "fill", "locator": "#name", "value": "Test Employee"},
   {"action": "select", "locator": "#role", "value": "employee"},
   {"action": "click", "locator": "text=Enter"}]}]
```
Actions: `fill`, `select`, `check`, `click`, `wait`. A step on a password field or with a secret-looking value is refused.

## Pages behind a login
Sign in yourself once in a browser opened with `playwright codegen --save-storage=state.json <url>`, then pass `--storage-state state.json`. The script never accepts a password and never stores the state file's contents in the map. Keep `state.json` out of the repository.

## What it does not do
Type into fields, submit forms, press anything that looks destructive, or store request bodies and headers. Network URLs are recorded with secret-looking query values replaced.

## Evidence handling
Screenshots can show personal data. Capture against synthetic or test data, store them with the handoff files (not in a public location), and tell the person if a real record appears in one.
