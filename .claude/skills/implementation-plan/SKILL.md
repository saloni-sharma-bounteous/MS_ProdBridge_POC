---
name: implementation-plan
description: Turn approved Jira stories (handoff/stories.json) into a short implementation plan - stack decisions, ordered waves of work, the critical path, and for each story the skill or step to use to build it. Use after create-jira-stories is approved, when asked "make an implementation plan", "what order do we build this in", "plan the build".
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
