# Portability: using these skills with any agent client or model

These skills are plain Markdown instructions plus optional Python scripts. They do not depend on one model or one client.

## Conventions every skill follows

- **Format**: `SKILL.md` with `name` and `description` frontmatter only, then Markdown. No client-specific frontmatter, tool names or slash syntax.
- **Capabilities, not tool names**: skills say "read a file", "run a command", "ask the person", "take a screenshot", "search the web". Use whichever tool your client offers for that. Where a skill names an MCP tool (Figma, Terraform, Playwright), match on the tool name and ignore any client prefix.
- **Paths**: relative to the skill folder (`<skill-dir>`), never to a client folder such as `.claude/`.
- **Scripts**: Python 3 standard library, run from a shell. No client features needed.
- **Missing capability**: say so plainly, skip that step, and mark the result as unverified. Never fake it.
- **Human gates**: stop and ask a named person; do not assume approval.
- **No model assumptions**: nothing relies on a specific model's context size or features. Keep each step small and explicit.

## Where each client loads skills

Run `node bin/cli.js init --target <client> -d <project>` from this repo, or copy the folders by hand.

| Client | Skills folder | Instructions file | MCP config |
|---|---|---|---|
| Claude Code | `.claude/skills` | `.claude/agents/orchestrator.md` | `.mcp.json` |
| Codex | `.agents/skills` | `AGENTS.md` | `.codex/config.toml` |
| GitHub Copilot (VS Code) | `.github/skills` | `.github/copilot-instructions.md` | `.vscode/mcp.json` |
| Antigravity | `.agent/skills` | `.agent/rules/` | MCP settings in the UI |
| Kiro | `.kiro/skills` | `.kiro/steering/` | `.kiro/settings/mcp.json` |

Client folder names change between versions; check your client's current docs if a skill is not picked up. As a fallback, tell the agent: "Read `<skills-dir>/<name>/SKILL.md` and follow it." Every client can do that.

## Browser, Figma and AWS tools

- **Screenshots** (`project-mindmap`, `figma-design-studio`): any browser tool from your client, the Playwright CLI, or headless Chrome/Edge.
- **Figma** and **AWS/Terraform** MCP servers: add them to your client's MCP config using the JSON shape in the skill's reference file; key names vary slightly by client.

## Stack-specific skills

`java-spring-service` (Spring Boot) and `aws-terraform-deploy` (AWS and Terraform) are tied to a technology stack on purpose, because that is what they build. They are still client- and model-agnostic. `implementation-plan` asks the tech lead to confirm the stack, and `team-code-review` takes its rules from the team's own standards file, so those two adapt to other stacks.
