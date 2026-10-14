---
name: project-mindmap
description: Build a visual mindmap of the current project showing its components, what each does and how they interact, rendered with the Playwright MCP and saved as a PNG. Use when asked for a mindmap, architecture map, component diagram or project overview.
---

# Project mindmap

Produce three files in `mindmap/` at the project root:

- `mindmap.json`: the structure you discover (components, flows)
- `mindmap.html`: an interactive, self-contained mindmap (no internet needed). Components that are web pages show a play badge; clicking one opens that page's live UI in a preview pane next to the map
- `mindmap.png`: a full-page screenshot taken with any headless-browser tool (see Requirements)
- `mindmap-preview.png`: a screenshot with one page preview open (only when the project has web pages)

## Requirements

- Python 3 (standard library only).
- A way to open a page and take a full-page screenshot. Any of these works: a browser/Playwright tool exposed by your agent client (MCP or built in), the Playwright CLI (`npx playwright screenshot --full-page`), or headless Chrome/Edge. If none is available, stop and tell the user how to add one for their client (see `PORTABILITY.md` in the skills folder). Do not fake the screenshot.

## Steps

### 1. Discover the project (read, don't guess)

The target is the folder the agent was started in (the workspace root), unless the user names another folder or project (for example "html-kyc"). In that case map that folder and write `mindmap/` inside it. If the name matches more than one folder, ask which one.

Look at the real files. Skip `.git`, `.venv`, `node_modules`, `__pycache__`, build output and lockfiles.

- List the folder tree (2-3 levels deep).
- Read the README, package/requirements files, config and `.env.example` (never print secrets from `.env`).
- Open each entry point and main module: scripts, apps, servers, agents, skills (`SKILL.md` files, wherever the client keeps them), MCP config.
- For each component note: what it is, what it does in one sentence, and which other components it calls, reads or writes.

Only include things you verified in the files. If something is unclear, say so in its `detail` instead of inventing behaviour.

### 2. Write `mindmap/mindmap.json`

Group components into **3-8 branches** (for example Skills, Backend, Data, Config, Integrations), with **at most 8 components per branch**. Keep names short (under 24 characters) and `role` to a few words, because they are printed inside the diagram.

```json
{
  "title": "Project name",
  "summary": "One or two sentences on what the project does.",
  "branches": [
    {
      "name": "Web app",
      "summary": "What this group is responsible for.",
      "children": [
        {
          "id": "app",
          "name": "kyc_app.py",
          "role": "Review desk UI",
          "path": "kyc_app.py",
          "detail": "How it works, in 1-3 sentences. Mention inputs, outputs and rules."
        }
      ]
    }
  ],
  "links": [
    { "from": "orchestrator", "to": "app", "label": "tests via browser" }
  ],
  "flow": [
    "The orchestrator opens the app URL in a browser.",
    "Findings are written to stories.json."
  ]
}
```

Page previews:

- A component whose `path` ends in `.html` or `.htm` gets a play badge automatically. `path` must be relative to the project root, for example `src/pages/login.html`.
- For a page that needs a running server, add `"preview": "http://localhost:8000"`. A full URL is used as given. Also set `path` to the file that starts it.
- Use `"preview"` on at most the 8 most important pages. Do not add it to scripts or data files.

Rules:

- Every component that appears in `links` needs a unique `id`. `from` and `to` must be existing ids.
- `links` show how components talk to each other (calls, reads, writes, triggers). Keep them to the 6-14 that matter and use verbs for labels.
- `flow` is the end-to-end story as ordered steps (4-8). Only include it if the project has a real sequence.

### 3. Build the HTML

Run from the project root. `<skill-dir>` is the folder holding this `SKILL.md` (project or user-level, whichever your client uses):

```
python <skill-dir>/scripts/build_mindmap.py mindmap/mindmap.json
```

It writes `mindmap/mindmap.html` and checks the JSON. If it prints errors (unknown link ids, missing names), fix the JSON and run it again.

### 4. Render a screenshot

Browser tools often block `file://` URLs, so serve the **project root** locally (not just `mindmap/`), because the page previews load files from elsewhere in the project.

1. From the project root, start a server in the background: `python -m http.server 8765`
2. Set the viewport to 1600 x 1000.
3. Open `http://localhost:8765/mindmap/mindmap.html`.
4. Take a full-page screenshot to `mindmap/mindmap.png`.
5. If any component has a play badge, find one, click it (with a scripted browser, e.g. a short Playwright script), wait for the preview pane to load, and take a second screenshot to `mindmap/mindmap-preview.png`. Check that the pane shows the real page and is not blank. If it is blank, fix the `path` or `preview` value in the JSON, rebuild and retry.
6. Look at the screenshots. Check that no labels overlap or are cut off, links are readable, and every component you found is present.
7. If something is cramped, shorten names or split an overloaded branch in the JSON, rebuild, reload and screenshot again. Stop after 3 attempts.
8. Stop the background server when done.

Use whichever browser capability your client provides; the steps are the same. If you cannot click, skip the preview screenshot and say so.

### 5. Report back

Tell the user the paths of `mindmap.html`, `mindmap.png` and (if made) `mindmap-preview.png`. Remind them that previews only load when the project is served, so to use the previews they should run `python -m http.server` from the project root and open `http://localhost:8000/mindmap/mindmap.html`. Also tell them which components have previews, then give a short plain-language summary: the branches, the 3-5 most important components, and the main flow. Mention anything you could not verify.

## Self-learning

At the end of every run, reflect on what went wrong or was slow, what the user corrected, and what was missing or unclear in this skill. If you find a concrete improvement, do not edit this skill on your own. Instead:

1. Propose it as a short list. For each item give the section affected, the exact change, and the reason (what it prevents next run).
2. Ask the user to approve, edit, or reject each item.
3. Apply only the approved items to this `SKILL.md` (or its scripts, templates or references), keeping edits small. Tell the user what changed.
4. If nothing needs changing, say so in one line. Never record secrets, personal data or one-off project details as lessons.
