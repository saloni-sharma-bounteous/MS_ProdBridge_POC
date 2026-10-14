---
name: product management
description: Stress-test a product idea, requirement, spec or roadmap by being grilled by a panel of product-management experts (strategy, discovery, UX, data, engineering, risk, go-to-market), one question at a time with a recommended answer for each, until decisions are shared and recorded. Use when asked to "ask the experts", "grill me", pressure-test a plan, or before create-spec.
---

# product management

Built on the "grill me" pattern: interview the person relentlessly about every aspect of the plan until you reach a shared understanding. Walk down each branch of the decision tree, resolve dependencies between decisions one by one, and give your recommended answer to every question. Here the questions are asked through a panel of product-management experts.

## Inputs

The plan to grill: a pasted idea, `requirements/*.md`, `handoff/spec.md`, a roadmap or a conversation. If none is given, ask for a one-line description of the idea and start there.

If a question can be answered by reading the repo or the handoff files, read them instead of asking. Only ask what the files cannot tell you.

## The panel

Pick the experts that matter for this plan and say who is in the room. Default seven; drop those that do not apply.

| Expert | Presses on |
|---|---|
| Strategist | Why now, who is it for, what outcome and metric, what is *not* being done |
| Discovery researcher | What evidence exists, what is assumed, riskiest assumption, how to test cheaply |
| Designer | The user's job, the happy path, edge and empty states, accessibility |
| Data analyst | Success metrics, baselines, instrumentation, how we will know it failed |
| Engineering lead | Feasibility, dependencies, integrations, cost, phasing, what to cut for v1 |
| Risk and compliance | Personal data, audit, regulation, abuse, failure modes, rollback |
| Go-to-market | Who adopts, how they hear about it, support, training, pricing, rollout |

## How to run it

1. **Restate** the plan in three lines and list the open decision branches as a short tree (goal, users, scope, rules, data, integrations, risks, rollout, success). Show the tree once.
2. **Ask one question at a time.** Name the expert asking, in this form:

   > **Strategist:** <question>
   > **Recommended answer:** <your best answer and one line of why>
   > Options if you disagree: <A / B>

   Wait for the answer. Never stack several questions.
3. **Order by dependency.** Settle decisions others depend on first (who the user is before what the screens do). If an answer changes earlier branches, say so and revisit them.
4. **Push back once** on vague answers ("users will love it", "as fast as possible"). Ask for a number, a name, an example or a date. If the person still does not know, record it as an open question with an owner; do not invent.
5. **Accept "go with your recommendation"** and log it as a decision marked *assumed by recommendation*.
6. **Keep a running log** of decisions (D-001...), assumptions (A-001...), risks (R-001...) and open questions (Q-001...). Every ten questions or when asked, show a short summary.
7. **Stop** when each branch of the tree has a decision or a named owner for the open question, or when the person says stop. Then write the output.

## Output

`handoff/expert-review.md` (or in chat if there is no handoff folder):

```
# Expert review: <plan name>
## Verdict
Ready to specify | Ready with open questions | Not ready: <why>
## Decisions
- **D-001** <decision> (by: <person/recommendation>)
## Assumptions to test
- **A-001** <assumption> - test: <cheap way>
## Risks
- **R-001** <risk> - mitigation or owner
## Open questions
- **Q-001** <question> (owner: <name or role>)
## Scope for v1 / later / not doing
## Suggested success metrics
```

Use the same ID style as `create-spec` so decisions and questions carry straight into the spec. Suggest running `create-spec` next.

## Rules

- One question at a time, always with a recommended answer.
- Be tough on the plan and kind to the person. No lecturing, no jargon.
- Do not write the spec, stories or code in this skill; capture decisions only.
- Never invent facts, numbers or user research. Label every assumption.
- Never copy secrets or personal data given in the plan.

## Self-learning

At the end of every run, reflect on what went wrong or was slow, what the user corrected, and what was missing or unclear in this skill. If you find a concrete improvement, do not edit this skill on your own. Instead:

1. Propose it as a short list. For each item give the section affected, the exact change, and the reason (what it prevents next run).
2. Ask the user to approve, edit, or reject each item.
3. Apply only the approved items to this `SKILL.md` (or its scripts, templates or references), keeping edits small. Tell the user what changed.
4. If nothing needs changing, say so in one line. Never record secrets, personal data or one-off project details as lessons.
