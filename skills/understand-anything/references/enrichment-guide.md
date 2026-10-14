# Enrichment guide

The script knows structure. Enrichment adds meaning. Write `enrichment.json` next to `graph.json`:

```json
{
  "summaries": {
    "fn:src/lib/scoring.ts#evaluate": "Runs the rating rules for one application and returns the decision inputs the screens display."
  },
  "community_labels": { "c3": "Application intake screen" },
  "concepts": [
    { "id": "concept:approval", "name": "Approval workflow",
      "description": "Where a request becomes approved or declined, and who is allowed to decide.",
      "nodes": ["fn:src/pages/ApplicationDetail.tsx#ApplicationDetail", "fn:src/lib/api.ts#updateStatus"] }
  ],
  "tours": [
    { "title": "From form to decision",
      "steps": [ { "node": "fn:src/pages/NewApplication.tsx#NewApplication", "why": "The user enters the request and sees the live assessment." },
                 { "node": "fn:src/lib/api.ts#saveApplication", "why": "The record is written straight from the browser." } ] }
  ]
}
```

## What to summarise

Do the nodes people will look at first: the top ten hubs, every entry point, every data store, and one node per community. A summary is one or two sentences: what it does, and why it matters or what is odd about it. Stay close to what the code does; do not guess at intent. If you are not sure, say what you could see.

## Concepts

A concept is a business idea that cuts across files (approval, screening, pricing, audit). Name it in the business's words, describe it in a sentence, and list the nodes where it lives. Three to eight concepts is typical. They are the bridge to the spec and to a portfolio wiki.

## Tours

A tour is an ordered reading path for a newcomer: four to eight steps, each with a reason. Offer one for the main user journey and one for the data path. Start at an entry point.

## Rules

- Every node id must exist; the script rejects unknown ids and skips stale ones after a rebuild.
- Summaries are at most 400 characters.
- No code, no secret values, no personal data. The script rejects text that looks like a credential.
- Mark uncertainty plainly ("appears to", "not confirmed").
- Do not edit `graph.json` by hand; keep everything in `enrichment.json` so a rebuild is safe.
