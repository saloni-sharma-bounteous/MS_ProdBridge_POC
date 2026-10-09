---
name: create-jira-stories
description: Turn handoff/spec.md into Jira epics and stories with Given/When/Then acceptance criteria, priority, size and dependencies, producing stories.json and optionally importing it into Jira. Use after create-spec, or when asked to "create Jira stories" or "import into Jira".
---

# Create Jira stories

Goal: `handoff/stories.json`, reviewed by a person, then created in Jira.

## Steps

1. **Draft** `handoff/stories.json` from `handoff/spec.md`. Group stories into epics the business recognises (for example "Capture customer", "Review case", "Reports"). Always include an early epic for foundations: database schema and the service skeleton (so other stories have somewhere to land), and one for security/audit if the spec has such requirements.
2. **Format** - this exact shape (what `scripts/jira_import.py` reads):

```json
{
  "app": {"name": "<app name>"},
  "epics": [
    {"id": "E-01", "title": "<epic title>", "goal": "<one sentence outcome>",
     "stories": [
       {"id": "S-001", "title": "<short title>",
        "description": "As a <role> I can <do X> so that <outcome>.",
        "priority": "P0",
        "effort": "M",
        "type": "feature",
        "acceptance_criteria": [
          "Given <context> When <action> Then <result>"
        ],
        "depends_on": [],
        "requirement_refs": ["FR-001", "BR-002"],
        "labels": []}
     ]}
  ]
}
```

   Priority `P0` / `P1` / `P2` (must / should / could). Effort `S` / `M` / `L` (split anything bigger than `L`). Type `feature`, `data`, `security`, `tech`. `depends_on` lists story ids that must finish first; no cycles.
3. **Check** before showing anyone:
   - every FR, BR, NF in the spec is cited by at least one story, or listed as out of scope with a reason
   - every story has at least two acceptance criteria in Given/When/Then, including a failure or boundary case
   - ids are unique and `depends_on` ids exist
   - a story is buildable by one engineer in a few days
4. **Review gate.** Give the business owner the stories in plain language (title, description, criteria) and the tech lead the same plus size and dependencies. Apply their changes. Do not record an approval for anyone; ask who approved and note it in the epic goal or Jira.
5. **Create in Jira** only after approval. Dry run first (default, sends nothing):
   ```
   python3 scripts/jira_import.py handoff/stories.json
   ```
   Then create, with credentials from the environment only (never in files or chat):
   ```
   set JIRA_BASE_URL=https://<org>.atlassian.net
   set JIRA_EMAIL=<email>
   set JIRA_API_TOKEN=<token>
   python3 scripts/jira_import.py handoff/stories.json --project <KEY> --apply
   ```
   Options and field mapping are documented at the top of the script. Re-running skips items already created. Confirm the project key with the person before `--apply`. If a Jira connector is available in the session, creating the issues through it is equivalent; use the same content.

## Rules

- Descriptions say what the user gets, not how it is built. Technical notes go in labels or an added `technical_notes` sentence at the end of the description.
- Never invent a rule the spec does not contain; add a question to the spec instead.
- Do not create issues in Jira for unapproved work.

## Output

`<handoff>/stories.json` and, after creation, `jira_import_state.json` (id to Jira key map) next to it.
