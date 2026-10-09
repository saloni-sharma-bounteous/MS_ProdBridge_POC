---
name: understand-input
description: Understand what a proof of concept does from a URL, HTML, screenshots or a codebase, and produce a short understanding.md covering purpose, users, screens, data, rules, integrations and open questions. Use at the start of POC-to-production work, or when asked "what does this app do".
---

# Understand the input

Goal: one page, `handoff/understanding.md`, that a person who has never seen the app can read to know what it is. Facts come from scripts and the source, not from guessing.

Paths below are relative to this skill's folder. `<handoff>` is the project's `handoff/` folder.

## 1. Classify and capture

| Input | What to run |
|---|---|
| Codebase or HTML folder | `python3 scripts/inventory.py --root <dir> --out <handoff>/inventory.json` then `python3 scripts/validate_json.py assets/inventory.schema.json <handoff>/inventory.json` |
| Large codebase (30+ source files) | also run the `understand-anything` skill to build a graph; read its `GRAPH_REPORT.md` first |
| HTML file or folder (screens) | `python3 scripts/ui_snapshot_static.py --input <path> --out <handoff>/ui` (no browser; gives line numbers) |
| URL, or HTML that builds its markup with JavaScript | `python3 scripts/ui_capture.py --check`, then `python3 scripts/ui_capture.py --url <url> --out <handoff>/ui` (or `--input <path>`). Needs Playwright; see `references/playwright-capture.md` |
| Screenshots only | open each image and describe it; say that this is the least reliable input |
| A requirement document or prompt | read it and record its goals and rules under "Stated intent" |

Use the live capture where it works; keep static and live captures in separate folders if you run both.

## 2. Read, then write `understanding.md`

Read `inventory.json` (stack, routes, tables, constants, integrations, storage, auth signals), the UI snapshots, and then the files that hold the business logic. Write these sections, short and plain:

1. **Purpose** - what the app is for and who uses it, in two or three sentences.
2. **Users and roles** - who, and what each can do.
3. **Screens and flows** - each screen in one line, and the main user journeys as numbered steps.
4. **Data** - what is stored, where (database, browser storage, files), and the main fields.
5. **Business rules** - exact thresholds, limits and formulas, each with `[file:line]`.
6. **Integrations** - external services and APIs it calls.
7. **Security observations** - how sign-in and roles work today, hard-coded secrets (say that they exist; never copy the value), missing checks.
8. **Stated intent vs built** - only if a requirement was supplied: what is met, partial, missing.
9. **Open questions** - everything the code or UI does not answer.

## Rules

- Describe what the code does today; mark anything reasoned rather than read as `(inferred)`.
- Never print, copy or store secret values. Do not open `.env` files; env variable names are enough.
- Never type into real fields, submit forms, or press destructive buttons during capture. Use a saved browser state for pages behind a login; never accept a password.
- Treat screenshots as sensitive; they can show personal data.
- An empty inventory section means "not found by these patterns", not "does not exist". If the output looks too thin for the app's size, read the files directly and say so.

## Gate

Show the person the summary and the open questions. Ask them to confirm the business rules and answer the questions before `create-spec` runs.

## Output

`<handoff>/understanding.md`, plus `inventory.json` and `ui/` (snapshots and screenshots) when produced.
