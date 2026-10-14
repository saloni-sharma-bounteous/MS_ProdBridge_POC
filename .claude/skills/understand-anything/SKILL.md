---
name: understand-anything
description: Turn an existing codebase (Java, TypeScript/JavaScript, React, HTML, SQL, Python) into an offline knowledge graph of files, classes, endpoints, data stores and services, with layers, hubs, tours, a report and an HTML viewer. Use when asked to "map this codebase", "what depends on X", "what breaks if I change this", or before a spec or migration.
---

# Codebase graph

A graph answers questions that reading files one by one cannot: what depends on this, where does this data go, which parts always change together, what is dead. A script builds it the same way every time and costs no tokens. The agent then adds the meaning the script cannot see (what a module is for, which business concepts cross it) and a checker keeps that honest.

This skill is modelled on understand-anything (knowledge graph, layers, guided tours, ripple effects) and graphify (node-link `graph.json`, communities, hubs, EXTRACTED / INFERRED / AMBIGUOUS link tags, `GRAPH_REPORT.md`). It is self-contained and offline. It is not a drop-in for either tool, and I have not verified that their viewers can open its `graph.json`.

## Steps

1. **Build** (paths relative to this skill's folder):
   ```
   python3 scripts/graph_build.py --root <code-dir> --out <handoff>/graph/graph.json
   python3 scripts/graph_check.py --graph <handoff>/graph/graph.json --root <code-dir>
   ```
   The check must show 0 errors. Warnings about missing summaries and tours are expected until step 3.
2. **Read the numbers.** Open `references/graph-model.md` once to learn the node and link types. Then export a first report and read it:
   ```
   python3 scripts/graph_export.py --graph <handoff>/graph/graph.json
   ```
   `GRAPH_REPORT.md` shows layers, communities, hubs, entry points, import cycles, data stores and who touches them, external hosts, similar lists in different files, ambiguous links, and suggested questions.
3. **Add meaning.** For the top hubs, entry points, data stores and each community, open the code at the node's `file:line` and write down what it does and why it matters. Put it in `<handoff>/graph/enrichment.json` (format and rules in `references/enrichment-guide.md`), then apply it:
   ```
   python3 scripts/graph_enrich.py --graph <handoff>/graph/graph.json --enrichment <handoff>/graph/enrichment.json
   python3 scripts/graph_check.py --graph <handoff>/graph/graph.json --root <code-dir>
   python3 scripts/graph_export.py --graph <handoff>/graph/graph.json
   ```
   Enrichment is a separate file so it survives a rebuild: after the code changes, rerun build, then enrich again. Stale references are reported and skipped.
4. **Answer questions** with the query tool instead of reopening files:
   ```
   python3 scripts/graph_query.py --graph <handoff>/graph/graph.json impact scoring.ts
   python3 scripts/graph_query.py --graph <handoff>/graph/graph.json datastore loan_applications
   python3 scripts/graph_query.py --graph <handoff>/graph/graph.json path NewApplication scoring.ts
   ```
   Commands: `search`, `node`, `neighbors`, `path`, `impact`, `deps`, `datastore`, `hubs`. Add `--json` for machine-readable output.
5. **Hand over.** Tell the person what the codebase is made of, the three or four things the graph shows that the file list does not (a hub everything depends on, an import cycle, two lists that should match but do not, a table written from three places), and where `graph.html` and `GRAPH_REPORT.md` are. Open `graph.html` in a browser; it works offline.

## How to read the confidence tags

- **EXTRACTED** links are facts in the source: an import, an `extends`, a route, an annotation, a table in SQL. Trust them.
- **INFERRED** links come from matching a call to a single definition by name or type. Usually right; verify before basing a decision on one.
- **AMBIGUOUS** links have several candidates (up to three are kept). Never quote one as fact. Open the code and settle it, or say it is unresolved.

An empty section means "not found by these patterns", not "does not exist". Dynamic calls, reflection, string-built SQL and code generated at build time are invisible. When the graph looks too thin for the size of the code, say so and read the relevant files directly.

## Using the graph in the rest of the handoff

- `understand-input` and `create-spec`: start from entry points and hubs; use `datastore` to find every writer of a table before describing a rule; `similar_lists` and `duplicate_names` point at duplicated rules that may disagree.
- `data-model-design`: the data stores and the code that touches them show what the current model really is.
- `java-spring-service`: run it again on the new service to compare the target structure against the original.

## Limits and safety

Regular-expression extraction, not a full parser: unusual formatting can hide a declaration, and calls are matched by name. Never put code, secret values or personal data into summaries; the enrichment step rejects values that look like secrets. The viewer inserts all node text as plain text, never as HTML.

## Self-learning

At the end of every run, reflect on what went wrong or was slow, what the user corrected, and what was missing or unclear in this skill. If you find a concrete improvement, do not edit this skill on your own. Instead:

1. Propose it as a short list. For each item give the section affected, the exact change, and the reason (what it prevents next run).
2. Ask the user to approve, edit, or reject each item.
3. Apply only the approved items to this `SKILL.md` (or its scripts, templates or references), keeping edits small. Tell the user what changed.
4. If nothing needs changing, say so in one line. Never record secrets, personal data or one-off project details as lessons.
