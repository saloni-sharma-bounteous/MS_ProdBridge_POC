# ProdBridge (MS_POC)

An AI-driven pipeline that takes a proof of concept (a URL, HTML files or a codebase) to production. It understands the POC, writes a spec, builds a Jira backlog, plans the work, generates a Spring Boot service, tests it in QA and releases it. It stops at a human approval gate after every stage.

The pipeline is built from Claude Code skills and an orchestrator agent. This repo holds the toolkit, the sample POC apps, and the files the pipeline has produced so far.

## How it works

| # | Stage | Skill | Output |
|---|-------|-------|--------|
| 1 | Understand the POC | `understand-input` (plus `understand-anything` for large codebases) | `handoff/understanding.md` |
| 2 | Write the spec | `create-spec` | `handoff/spec.md` |
| 3 | Create the backlog | `create-jira-stories` | `handoff/stories.json`, then Jira |
| 4 | Plan the build | `implementation-plan` | `handoff/plan.md` |
| 5 | Build | `data-model-design`, then `java-spring-service` | `handoff/data-model/`, service code |
| 6 | Release to QA | `release-to-qa` | `handoff/qa-report.md` |
| 7 | Release to production | `release-to-prod` | `handoff/release-plan.md` |

A stage is skipped only if its output already exists and is current.

### Human gates

After each stage the orchestrator shows a short summary (what was produced, open questions, what it could not verify) and waits for a named person's decision. It never approves on anyone's behalf, never reveals secrets, never changes the prototype, and never deploys to production without the release-to-prod gate and named approvals.

## Getting started

Requirements: Claude Code, Python 3, and Node.js (the Playwright MCP runs through `npx`).

1. Copy `.env.example` to `.env` and fill in your Jira settings (the `JIRA_*` variables used by `create-jira-stories`). `.env` is git-ignored; never commit it. Create the virtual environment first if `.venv/` does not exist (`python -m venv .venv`).
2. Activate the environment and load `.env` (PowerShell, from the project root):
   ```
   . .\Scripts\activate_env.ps1
   ```
3. Start Claude Code in this folder and run the `orchestrator` agent, giving it a POC to take to production. You can also run any skill on its own, for example `/project-mindmap`.
4. Ask "what next" at any time. The orchestrator checks which `handoff/` files exist and answers from that.

The Playwright MCP is configured in `.mcp.json`. It is used for UI capture, QA tests and rendering the mindmap. If it fails to connect, check that `npx` works and restart Claude Code.

## Project layout

```
.claude/
  agents/orchestrator.md        pipeline entry point
  prompts/orchestrator.prompt.md  the same flow as a prompt
  skills/                       one folder per stage (see table above), plus project-mindmap
apps/
  html-kyc-onboarding-desk/     sample POC: KYC onboarding web app (has its own README)
  Live_Test_App/                second app (ui.py) and its pipeline outputs in handoff/:
                                understanding, spec, stories, data-model (DDL, ERD,
                                Flyway), UI snapshots, Jira import state
requirements/
  REQ-0044-kyc-onboarding-desk.md   business requirement for the KYC desk
mindmap/                        mindmaps (ProdBridge, plus kyc-desk/)
Scripts/activate_env.ps1        activates .venv and loads .env
tests/run_tests.py              toolkit test suite
.env.example                    template for .env
.mcp.json                       Playwright MCP configuration
```

New pipeline runs write to `handoff/` at the project root.

## Skills

- **understand-input**: inventories the POC and captures its UI, then writes `understanding.md`.
- **understand-anything**: builds a knowledge graph of a large codebase.
- **create-spec**: writes a short production spec with numbered requirements and business rules.
- **create-jira-stories**: turns the spec into epics and stories with Given/When/Then criteria, and can import them to Jira.
- **implementation-plan**: orders the stories into waves and picks the skill for each.
- **data-model-design**: designs the schema and generates PostgreSQL DDL, an ER diagram and a migration plan.
- **java-spring-service**: scaffolds a Spring Boot 4 / Java 21 service and implements the rules tests-first.
- **release-to-qa**: deploys to QA and runs Playwright tests against the acceptance criteria.
- **release-to-prod**: readiness gate, rollback plan, named approvals, deployment and post-release checks.
- **project-mindmap**: builds an interactive mindmap and a PNG of a project.

## Mindmaps

- ProdBridge (this project): `mindmap/mindmap.html`
- KYC Onboarding Desk: `mindmap/kyc-desk/mindmap.html`

## Notes and caveats

- `tests/run_tests.py` refers to `skills/`, `evals/`, `examples/` and `tools/` folders that are not in this repo, so it will not run as it stands.
- The sample KYC app is a proof of concept with known issues (inconsistent scoring copies, hard-coded credentials, unchecked quick approve). See its README.
- Secrets live only in `.env` and are never printed by the skills.
