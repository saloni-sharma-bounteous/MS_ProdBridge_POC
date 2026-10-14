# ProdBridge (MS_POC)

An AI-driven pipeline that takes a proof of concept (a URL, HTML files or a codebase) to production. It understands the POC, writes a spec, builds a Jira backlog, plans the work, generates a Spring Boot service, tests it in QA and releases it. It stops at a human approval gate after every stage.

The pipeline is built from agent skills (plain `SKILL.md` files) and an orchestrator agent. It is not tied to one model or client: it installs for Claude Code, Codex, GitHub Copilot, Antigravity and Kiro (see `skills/PORTABILITY.md`). This repo holds the toolkit, the sample POC apps, and the files the pipeline has produced so far.

## How it works

| # | Stage | Skill | Output |
|---|-------|-------|--------|
| 1 | Understand the POC | `understand-input` (plus `understand-anything` for large codebases) | `handoff/understanding.md` |
| 2 | Grill the plan | `product-management` (ask-the-experts) | `handoff/expert-review.md` |
| 3 | Write the spec | `create-spec` | `handoff/spec.md` |
| 4 | Create the backlog | `create-jira-stories` | `handoff/stories.json`, then Jira |
| 5 | Plan the build | `implementation-plan` | `handoff/plan.md` |
| 6 | Design (if there are screens) | `figma-design-studio` | `design/` |
| 7 | Build | `data-model-design`, `java-spring-service`, then `aws-terraform-deploy` (plan only) | `handoff/data-model/`, service code, Terraform |
| 8 | Code review | `team-code-review` | `handoff/code-review.md` |
| 9 | Release to QA | `release-to-qa` | `handoff/qa-report.md` |
| 10 | Release to production | `release-to-prod` | `handoff/release-plan.md` |

`project-mindmap` is optional and can run at any point.

A stage is skipped only if its output already exists and is current.

### Human gates

After each stage the orchestrator shows a short summary (what was produced, open questions, what it could not verify) and waits for a named person's decision. It never approves on anyone's behalf, never reveals secrets, never changes the prototype, and never deploys to production without the release-to-prod gate and named approvals.

## Requirements

| Needed for | Requirement | Notes |
|---|---|---|
| Everything | An agent client: Claude Code, Codex, GitHub Copilot (VS Code), Antigravity or Kiro | Any client that can read `SKILL.md` files works (see "Other clients") |
| Installer, Playwright MCP | Node.js 18 or later (`node`, `npx`) | |
| Skill scripts | Python 3 (standard library only) | Create a venv if you like: `python -m venv .venv` |
| UI capture, QA tests, mindmap PNG | `pip install playwright` then `playwright install chromium` | Or use the Playwright MCP, or headless Chrome/Edge. Set `QA_BROWSER_CHANNEL` (for example `msedge`) to use an installed browser |
| `java-spring-service` | JDK 21 and Maven (`mvn -B verify`) | |
| Java tests (Testcontainers), Terraform MCP | Docker, running | |
| AWS Core MCP | `uv` / `uvx` | |
| `aws-terraform-deploy` | Terraform CLI and AWS credentials | Optional: it only produces a plan, and says so if these are missing |
| `create-jira-stories` import | Jira Cloud URL, email and API token | Set in `.env` |
| `figma-design-studio` (native Figma frames) | Figma MCP connected and a Figma file URL | Optional: without it you get Figma-ready boards, PNGs and tokens |

Secrets live only in `.env` (copy `.env.example`). It is git-ignored; never commit it.

## Getting started

1. Clone this repo and `cd` into it.
2. `cp .env.example .env` and fill in `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` (and `QA_BROWSER_CHANNEL` if needed).
3. Install the toolkit for your client (see the sections below). General form:
   ```
   node bin/cli.js init --target <claude|codex|copilot|antigravity|kiro|all> [-d <project>] [--force] [--dry-run]
   node bin/cli.js list      # show the skills
   ```
   Once published: `npx prodbridge-agents init --target <tool>`. Existing files are kept unless you pass `--force`; managed blocks in shared files (`AGENTS.md`, `copilot-instructions.md`) are refreshed and your own text is preserved. Use `-d <project>` to install into another project, which is the normal case for Codex and Copilot.
4. Start your client in the project folder and run the orchestrator with a POC to take to production.
5. Ask "what next" at any time. The orchestrator checks which `handoff/` files exist and answers from that.

### Claude Code

```
node bin/cli.js init --target claude
```
Writes `.claude/skills/`, `.claude/agents/orchestrator.md`, `.claude/prompts/orchestrator.prompt.md` and merges the MCP servers into `.mcp.json`.
- Start `claude` in the folder, approve the project MCP servers when asked, and run the `orchestrator` agent (or `/agents`). Run a single skill with `/<skill-name>`, for example `/project-mindmap`.
- Check MCP with `/mcp`. If a server shows as failed, see "Troubleshooting".

### OpenAI Codex (CLI / IDE)

```
node bin/cli.js init --target codex -d <project>
```
Writes `.agents/skills/`, a managed block in `AGENTS.md` (orchestrator rules plus a skill index) and `.codex/config.toml` (MCP servers).
- Codex reads `.codex/config.toml` only for trusted projects. If MCP servers are missing, copy that block into `~/.codex/config.toml`.
- Needs a recent Codex CLI for native skills. On older versions `AGENTS.md` still points Codex at every `SKILL.md`.
- Start `codex` in the project and ask it to act as the orchestrator for your POC.

### GitHub Copilot (VS Code)

```
node bin/cli.js init --target copilot -d <project>
```
Writes `.github/skills/`, `.github/copilot-instructions.md` (managed block), `.github/agents/orchestrator.agent.md`, `.github/prompts/orchestrator.prompt.md` and `.vscode/mcp.json`.
- Use Copilot Chat in agent mode: pick the `orchestrator` agent or type `/orchestrator`.
- Start the MCP servers from `.vscode/mcp.json` (the "Start" lens above each server).

### Antigravity

```
node bin/cli.js init --target antigravity -d <project>
```
Writes `.agent/skills/`, `.agent/rules/prodbridge.md` and `.agent/workflows/orchestrator.md`. Run the `/orchestrator` workflow.
MCP is not written automatically: add the servers from `mcp/mcp.json` in the Antigravity MCP settings (at least `npx @playwright/mcp@latest`).

### Kiro

```
node bin/cli.js init --target kiro -d <project>
```
Writes `.kiro/skills/`, `.kiro/steering/prodbridge.md` (always included) and `.kiro/settings/mcp.json`. The steering file tells the agent where each `SKILL.md` is, so it works even if your Kiro version does not load `.kiro/skills` natively.

### Other clients or models (Cursor, Windsurf, Gemini CLI, a plain chat model)

The skills are plain Markdown plus standard-library Python, so no installer is needed.
1. Copy `skills/` (and `agents/orchestrator.md`) into your client's instructions or skills folder, or just leave them in this repo.
2. Give the client this prompt: "Read `agents/orchestrator.md` and follow it. Before each stage, read `skills/<name>/SKILL.md` and follow it exactly."
3. Add the MCP servers from `mcp/mcp.json` to your client's MCP config if it supports MCP. Without MCP, skills that need a browser fall back to the Playwright CLI or headless Chrome/Edge, and anything that cannot be done is marked unverified.

See `skills/PORTABILITY.md` for the conventions every skill follows and the folder each client uses.

### MCP servers

Defined once in `mcp/mcp.json` (copied to `.mcp.json` for Claude Code):

| Server | Needs | Used for |
|---|---|---|
| playwright | `npx` | UI capture, QA tests, mindmap rendering |
| aws-knowledge | internet (remote) | AWS documentation lookup |
| aws-core | `uvx` | AWS architecture guidance |
| terraform | Docker running | Terraform registry and docs |

Remove any you do not need. Figma is optional and added separately by you.

### Troubleshooting

- MCP server "connection closed": check the prerequisite in the table above (`npx` works, Docker is running, `uvx` is installed), then restart the client.
- Skill not picked up: client folder names change between versions. Tell the agent "Read `<skills-dir>/<name>/SKILL.md` and follow it."
- Windows: run the commands from PowerShell or Git Bash; use `python` instead of `python3` if needed.
- Skill names: the orchestrator refers to the grilling stage as `ask-the-experts`, but the skill folder is `skills/product-management`. Point the agent at that folder if it cannot find it.

### Self-learning skills

Every skill ends with a self-learning step. After a run it proposes concrete improvements to its own `SKILL.md`, and changes nothing until you approve each item. Re-run `init --force` to push approved edits to the client folders.

## Project layout

```
skills/, agents/, prompts/      single source for the toolkit (same layout as prodbridge-agents)
bin/cli.js, src/installer.js    installer: `node bin/cli.js init --target claude|codex|copilot|antigravity|kiro -d <project>`
mcp/mcp.json                    MCP servers the installer registers per tool
package.json                    npm package metadata (bin, files)
.claude/                        generated by `init --target claude`; used by Claude Code in this repo
apps/
  html-kyc-onboarding-desk/     sample POC: KYC onboarding web app (has its own README)
  Live_Test_App/                second app (ui.py) and its pipeline outputs in handoff/:
                                understanding, spec, stories, data-model (DDL, ERD,
                                Flyway), UI snapshots, Jira import state
requirements/
  REQ-0044-kyc-onboarding-desk.md   business requirement for the KYC desk
mindmap/                        mindmaps (ProdBridge, plus kyc-desk/)
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
- **team-code-review**: reviews a diff or PR against the team's coding standards and best practices, with findings by severity.
- **product-management** (also called ask-the-experts): grills you on a product idea or plan through a panel of PM experts, one question at a time, and records decisions.
- **project-mindmap**: builds an interactive mindmap and a PNG of a project.

## Mindmaps

- KYC Onboarding Desk: `mindmap/kyc-desk/mindmap.html`

## Notes and caveats

- `tests/run_tests.py` refers to `skills/`, `evals/`, `examples/` and `tools/` folders that are not in this repo, so it will not run as it stands.
- The sample KYC app is a proof of concept with known issues (inconsistent scoring copies, hard-coded credentials, unchecked quick approve). See its README.
- Secrets live only in `.env` and are never printed by the skills.
