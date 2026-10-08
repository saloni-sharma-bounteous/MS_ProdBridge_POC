---
name: project-mindmap
description: Build a visual mindmap of the current project showing every component, what it does, and how the components work together, then render it with the Playwright MCP and save a PNG. Use this whenever the user asks for a mindmap, architecture map, project overview, component diagram, "how does this project work", or wants to visualize or explain the codebase, even if they do not say "mindmap".
---

# Project mindmap

Produce three files in `mindmap/` at the project root:

- `mindmap.json`: the structure you discover (components, flows)
- `mindmap.html`: an interactive, self-contained mindmap (no internet needed). Components that are web pages show a play badge; clicking one opens that page's live UI in a preview pane next to the map
- `mindmap.png`: a full-page screenshot taken with the Playwright MCP
- `mindmap-preview.png`: a screenshot with one page preview open (only when the project has web pages)

## Requirements

- Python 3 (standard library only).
- The **Playwright MCP** server. If its tools (`browser_navigate`, `browser_take_screenshot`) are not available, stop and tell the user to run
  `claude mcp add playwright npx @playwright/mcp@latest`, restart Claude Code, and try again. Do not fake the screenshot.

## Steps

### 1. Discover the project (read, don't guess)

The target is the folder Claude Code was started in, unless the user names another folder or project (for example "html-kyc"). In that case map that folder and write `mindmap/` inside it. If the name matches more than one folder, ask which one.

Look at the real files. Skip `.git`, `.venv`, `node_modules`, `__pycache__`, build output and lockfiles.

- List the folder tree (2-3 levels deep).
- Read the README, package/requirements files, config and `.env.example` (never print secrets from `.env`).
- Open each entry point and main module: scripts, apps, servers, agents, skills (`.claude/skills/*/SKILL.md`), MCP config.
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

Run from the project root. This skill may live in the project (`.claude/skills/project-mindmap`) or globally (`~/.claude/skills/project-mindmap`, which is `%USERPROFILE%\.claude\skills\project-mindmap` on Windows). Use whichever exists:

```
python .claude/skills/project-mindmap/scripts/build_mindmap.py mindmap/mindmap.json
python ~/.claude/skills/project-mindmap/scripts/build_mindmap.py mindmap/mindmap.json
```

It writes `mindmap/mindmap.html` and checks the JSON. If it prints errors (unknown link ids, missing names), fix the JSON and run it again.

### 4. Render with the Playwright MCP

The Playwright MCP blocks `file://` URLs, so serve the **project root** locally (not just `mindmap/`), because the page previews load files from elsewhere in the project.

1. From the project root, start a server in the background: `python -m http.server 8765`
2. `browser_resize` to width 1600, height 1000.
3. `browser_navigate` to `http://localhost:8765/mindmap/mindmap.html`.
4. `browser_take_screenshot` with `fullPage: true` and `filename: mindmap/mindmap.png`.
5. If any component has a play badge, use `browser_snapshot` to find one, `browser_click` it, wait for the preview pane to load, and take a second screenshot to `mindmap/mindmap-preview.png`. Check that the pane shows the real page and is not blank. If it is blank, fix the `path` or `preview` value in the JSON, rebuild and retry.
6. Look at the screenshots. Check that no labels overlap or are cut off, links are readable, and every component you found is present.
7. If something is cramped, shorten names or split an overloaded branch in the JSON, rebuild, reload and screenshot again. Stop after 3 attempts.
8. Stop the background server when done.

Tool names may appear with a prefix such as `mcp__playwright__browser_navigate`. Use whichever form is available.

### 5. Report back

Tell the user the paths of `mindmap.html`, `mindmap.png` and (if made) `mindmap-preview.png`. Remind them that previews only load when the project is served, so to use the previews they should run `python -m http.server` from the project root and open `http://localhost:8000/mindmap/mindmap.html`. Also tell them which components have previews, then give a short plain-language summary: the branches, the 3-5 most important components, and the main flow. Mention anything you could not verify.
