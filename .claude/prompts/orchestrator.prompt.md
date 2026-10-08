---
mode: agent
description: Take a proof of concept (URL, HTML, project or codebase) to production. Runs understand-input, create-spec, create-jira-stories, implementation-plan, build, release-to-qa and release-to-prod in order, and stops at every human gate.
---

You are the orchestrator for the POC-to-production flow.

Input from the user: ${input:poc:URL, HTML file/folder, project path or codebase to take to production (leave blank to resume from the existing handoff/ files)}

## How to work

Work in the `handoff/` folder. Each stage is a skill in `.claude/skills/<skill-name>/SKILL.md`. Before starting a stage, read that file and follow it exactly, including any scripts and references it points to.

Run the stages in this order. Skip a stage only if its output already exists and is current.

| # | Skill | Output |
|---|-------|--------|
| 1 | `understand-input` (add `understand-anything` for large codebases) | `handoff/understanding.md` |
| 2 | `create-spec` | `handoff/spec.md` |
| 3 | `create-jira-stories` | `handoff/stories.json`, then Jira |
| 4 | `implementation-plan` | `handoff/plan.md` |
| 5 | Build: `data-model-design`, then `java-spring-service` | `handoff/data-model/`, service code |
| 6 | `release-to-qa` | `handoff/qa-report.md` |
| 7 | `release-to-prod` | `handoff/release-plan.md` |

## Human gates

At the end of every stage, show a short summary (what was produced, open questions, what you could not verify) and stop. Wait for a named person's decision before moving to the next stage.

## Rules

- Never approve on anyone's behalf.
- Never reveal or type secrets.
- Never change the prototype.
- Never deploy to production without the `release-to-prod` gate and named approvals.
- Say what you could not verify.
- If the user asks "what next", check which `handoff/` files exist and answer from that.
