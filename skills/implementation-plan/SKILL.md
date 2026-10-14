---
name: implementation-plan
description: Turn approved Jira stories (handoff/stories.json) into a short implementation plan - stack decisions, ordered waves, critical path, and the skill or step for each story. Use after create-jira-stories, or when asked "what order do we build this in".
---

# Implementation plan

Goal: `handoff/plan.md`, so an engineer can pick up any story and know the next action.

## Preconditions

`handoff/stories.json` exists and a named person has approved it. If not, stop and say so; do not plan unapproved scope.

## Steps

1. **Confirm the stack** with the tech lead; record answers at the top of the plan. Defaults: Java 21 + Spring Boot 4, PostgreSQL with Flyway migrations, Maven, Docker, JUnit + Testcontainers, Playwright for UI tests. Anything else is a decision to list.
2. **Order the work** into waves by `depends_on` (a story is in the earliest wave after all its dependencies). Wave 1 must hold the data model and the service skeleton. Put `P0` ahead of `P1` within a wave. Stories in the same wave can run in parallel.
3. **Find the critical path**: the longest dependency chain. Name it, since it sets the earliest finish.
4. **Assign the method per story**:
   - schema/data stories: `data-model-design`
   - service and rule stories: `java-spring-service` (tests first)
   - UI-facing stories: wire the screen to the API, then test with Playwright in `release-to-qa`
   - anything else: say the concrete steps
5. **List risks and open decisions** (unclear rules, external system access, missing environments, data migration).
6. **Gate**: the tech lead accepts the order, critical path and decisions. If they disagree, change the story dependencies and re-plan; do not reorder around a dependency.

## Format of `handoff/plan.md`

```
# Implementation plan: <app>
## Stack decisions        (confirmed / to confirm)
## Waves
### Wave 1
| Story | Title | Size | Depends on | Method |
...
## Critical path          S-001 -> S-004 -> ...
## Definition of done     tests written first and passing; business rules cite spec ids; no secrets in code; migration included; reviewed
## Release path           release-to-qa, then release-to-prod
## Risks and open decisions
```

## Rules

- Every approved story appears exactly once.
- No calendar dates; people add those against their own capacity.
- If a story is too vague to start, send it back to `create-jira-stories`.

## Output

`<handoff>/plan.md`

## Self-learning

At the end of every run, reflect on what went wrong or was slow, what the user corrected, and what was missing or unclear in this skill. If you find a concrete improvement, do not edit this skill on your own. Instead:

1. Propose it as a short list. For each item give the section affected, the exact change, and the reason (what it prevents next run).
2. Ask the user to approve, edit, or reject each item.
3. Apply only the approved items to this `SKILL.md` (or its scripts, templates or references), keeping edits small. Tell the user what changed.
4. If nothing needs changing, say so in one line. Never record secrets, personal data or one-off project details as lessons.
