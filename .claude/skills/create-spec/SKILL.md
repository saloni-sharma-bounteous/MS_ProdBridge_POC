---
name: create-spec
description: Write a short specification for the production version of an app from handoff/understanding.md: scope, actors, numbered requirements, business rules, data, screens, integrations, non-functional needs, out of scope and open questions. Use after understand-input, or when asked to "write the spec" or "what are we building".
---

# Create the spec

Goal: `handoff/spec.md`, one page-or-few document. A reader should be able to say "yes, build that" or "no, change X" from it alone. If a sentence does not help someone build or review, leave it out.

## Inputs

`handoff/understanding.md` (required; run `understand-input` first) and any requirement text. If the understanding has open questions that block a requirement, ask the person; do not invent a rule.

## Format

Use exactly these sections, in this order. Each requirement is one bullet with a stable ID, because Jira stories, the data model and tests will cite it.

```
# Spec: <app name>

## 1. Scope
One paragraph: what is being built and for whom. Then "Out of scope:" as a short list.

## 2. Actors
- <role>: what they can do.

## 3. Functional requirements
- **FR-001** <actor can do X; system responds Y>

## 4. Business rules
- **BR-001** <rule with exact thresholds, limits, formulas; say if limits are inclusive>

## 5. Data
- **DM-001** <entity: key fields, status values, who owns it, retention if known>

## 6. Screens
- **UI-001** <screen: purpose, main actions, who sees it>

## 7. Integrations
- **IN-001** <system, what data, what happens on failure>

## 8. Non-functional
- **NF-001** <security, audit, performance, availability, accessibility - measurable where possible>

## 9. Open questions
- **Q-001** <question> (owner: <name or role>)
```

Keep the `- **XX-000**` bullet form exactly; `data-model-design` reads these IDs.

## Rules

- State the target behaviour, not the prototype's accidents. Where the prototype does something questionable (hard-coded PIN, client-side checks, duplicated rules that disagree), the spec states the correct requirement and Q-items record the decision needed.
- One testable fact per bullet. Exact values, never rounded.
- Every FR and BR is something a person could check with Given/When/Then later.
- Plain words a business owner can read. No code names unless unavoidable.
- Always cover: who may do what (roles), what is audited, what personal data is held and how it is protected, what happens on error.
- Never copy secret values.

## Gate

Ask the business owner to confirm Sections 3-4 and answer the open questions, and a tech lead to confirm Sections 5, 7 and 8. Apply corrections. Do not start Jira stories until the owner has approved.

## Output

`<handoff>/spec.md`
