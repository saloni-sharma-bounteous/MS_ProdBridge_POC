'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SKILLS_SRC = path.join(ROOT, 'skills');
const BEGIN = '<!-- BEGIN prodbridge-agents (managed) -->';
const END = '<!-- END prodbridge-agents (managed) -->';
const TOML_BEGIN = '# BEGIN prodbridge-agents (managed)';
const TOML_END = '# END prodbridge-agents (managed)';

// Where each tool looks for skills. Source skills reference `.claude/skills`
// in a few places; those are rewritten to the target's folder.
const TARGETS = {
  claude: { skillsDir: '.claude/skills' },
  codex: { skillsDir: '.agents/skills' },
  copilot: { skillsDir: '.github/skills' },
  antigravity: { skillsDir: '.agent/skills' },
  kiro: { skillsDir: '.kiro/skills' },
};

const readText = (p) => fs.readFileSync(p, 'utf8').replace(/^﻿/, '');

function stripFrontmatter(text) {
  return text.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '').trim();
}

function frontmatter(text) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  const out = {};
  if (!m) return out;
  for (const line of m[1].split(/\r?\n/)) {
    const kv = line.match(/^([A-Za-z_-]+):\s*(.*)$/);
    if (kv) out[kv[1]] = kv[2].trim();
  }
  return out;
}

function listSkills() {
  return fs
    .readdirSync(SKILLS_SRC, { withFileTypes: true })
    .filter((d) => d.isDirectory() && fs.existsSync(path.join(SKILLS_SRC, d.name, 'SKILL.md')))
    .map((d) => {
      const fm = frontmatter(readText(path.join(SKILLS_SRC, d.name, 'SKILL.md')));
      return { name: fm.name || d.name, dir: d.name, description: fm.description || '' };
    });
}

function makeCtx({ dir, force, dryRun }) {
  const log = { lines: [], notes: [], written: 0, skipped: 0 };
  const rel = (p) => path.relative(dir, p).split(path.sep).join('/');
  const ensure = (p) => !dryRun && fs.mkdirSync(path.dirname(p), { recursive: true });
  return {
    log,
    dir,
    // Write a file; existing files are kept unless force is set.
    write(p, data, { overwrite = force } = {}) {
      if (fs.existsSync(p) && !overwrite) {
        log.skipped++;
        log.lines.push(`  skip   ${rel(p)} (exists, use --force)`);
        return;
      }
      ensure(p);
      if (!dryRun) fs.writeFileSync(p, data);
      log.written++;
      log.lines.push(`  write  ${rel(p)}`);
    },
    // Insert or refresh a managed block inside a file the user may also edit.
    block(p, body, begin = BEGIN, end = END) {
      const block = `${begin}\n${body.trim()}\n${end}\n`;
      let existing = fs.existsSync(p) ? readText(p) : '';
      const a = existing.indexOf(begin);
      const b = existing.indexOf(end);
      let next;
      if (a !== -1 && b > a) next = existing.slice(0, a) + block + existing.slice(b + end.length).replace(/^\r?\n/, '');
      else next = existing ? existing.replace(/\s*$/, '\n\n') + block : block;
      ensure(p);
      if (!dryRun) fs.writeFileSync(p, next);
      log.written++;
      log.lines.push(`  block  ${rel(p)}`);
    },
    // Merge the MCP servers from mcp/mcp.json into a JSON config under the given key.
    mergeMcp(p, key, extra = {}) {
      const src = JSON.parse(readText(path.join(ROOT, 'mcp', 'mcp.json'))).mcpServers;
      let cfg = {};
      if (fs.existsSync(p)) {
        try {
          cfg = JSON.parse(readText(p));
        } catch (e) {
          log.skipped++;
          log.lines.push(`  skip   ${rel(p)} (not valid JSON, add the MCP server by hand)`);
          return;
        }
      }
      cfg[key] = cfg[key] || {};
      let added = 0;
      for (const [name, def] of Object.entries(src)) {
        if (!cfg[key][name]) {
          cfg[key][name] = { ...extra, ...def };
          added++;
        }
      }
      if (!added) {
        log.skipped++;
        log.lines.push(`  skip   ${rel(p)} (MCP servers already present)`);
        return;
      }
      ensure(p);
      if (!dryRun) fs.writeFileSync(p, JSON.stringify(cfg, null, 2) + '\n');
      log.written++;
      log.lines.push(`  merge  ${rel(p)}`);
    },
  };
}

// Copy skills verbatim (binary-safe); rewrite .claude/skills paths in markdown only.
function copySkills(ctx, skillsDir) {
  const dest = path.join(ctx.dir, skillsDir);
  const walk = (src, out) => {
    for (const e of fs.readdirSync(src, { withFileTypes: true })) {
      const s = path.join(src, e.name);
      const o = path.join(out, e.name);
      if (e.isDirectory()) {
        if (e.name === '__pycache__') continue;
        walk(s, o);
      } else if (path.extname(e.name) === '.md') {
        ctx.write(o, readText(s).split('.claude/skills').join(skillsDir));
      } else {
        ctx.write(o, fs.readFileSync(s));
      }
    }
  };
  walk(SKILLS_SRC, dest);
}

const orchestratorBody = (skillsDir) =>
  stripFrontmatter(readText(path.join(ROOT, 'agents', 'orchestrator.md'))).split('.claude/skills').join(skillsDir);

function skillIndex(skillsDir) {
  return listSkills()
    .map((s) => `- \`${s.name}\` (${skillsDir}/${s.dir}/SKILL.md): ${s.description}`)
    .join('\n');
}

function instructions(skillsDir) {
  return `## ProdBridge: POC to production

${orchestratorBody(skillsDir)}

### Skills

Each stage is a skill. Before starting a stage, open its SKILL.md and follow it exactly, including the scripts and references it points to (paths in a SKILL.md are relative to that skill's folder).

${skillIndex(skillsDir)}`;
}

function installClaude(ctx) {
  const { skillsDir } = TARGETS.claude;
  copySkills(ctx, skillsDir);
  ctx.write(path.join(ctx.dir, '.claude/agents/orchestrator.md'), readText(path.join(ROOT, 'agents', 'orchestrator.md')));
  ctx.write(
    path.join(ctx.dir, '.claude/prompts/orchestrator.prompt.md'),
    readText(path.join(ROOT, 'prompts', 'orchestrator.prompt.md'))
  );
  ctx.mergeMcp(path.join(ctx.dir, '.mcp.json'), 'mcpServers');
}

function installCodex(ctx) {
  const { skillsDir } = TARGETS.codex;
  copySkills(ctx, skillsDir);
  ctx.block(path.join(ctx.dir, 'AGENTS.md'), instructions(skillsDir));
  const srv = JSON.parse(readText(path.join(ROOT, 'mcp', 'mcp.json'))).mcpServers;
  const toml = Object.entries(srv)
    .map(([n, d]) => {
      let t = `[mcp_servers.${n}]\n`;
      if (d.url) return t + `url = ${JSON.stringify(d.url)}`;
      t += `command = ${JSON.stringify(d.command)}\nargs = ${JSON.stringify(d.args || [])}`;
      if (d.env) {
        const env = Object.entries(d.env).map(([k, v]) => `${JSON.stringify(k)} = ${JSON.stringify(v)}`);
        t += `\n\n[mcp_servers.${n}.env]\n${env.join('\n')}`;
      }
      return t;
    })
    .join('\n\n');
  ctx.block(path.join(ctx.dir, '.codex/config.toml'), toml, TOML_BEGIN, TOML_END);
  ctx.log.notes.push(
    'Codex reads .codex/config.toml only for trusted projects. If the MCP servers (Playwright, AWS, Terraform) are not picked up, copy that block into ~/.codex/config.toml. Skills in .agents/skills need a recent Codex CLI; on older versions AGENTS.md alone still tells Codex where each SKILL.md is.'
  );
}

function installCopilot(ctx) {
  const { skillsDir } = TARGETS.copilot;
  copySkills(ctx, skillsDir);
  ctx.block(path.join(ctx.dir, '.github/copilot-instructions.md'), instructions(skillsDir));
  const desc = frontmatter(readText(path.join(ROOT, 'agents', 'orchestrator.md'))).description || '';
  ctx.write(
    path.join(ctx.dir, '.github/agents/orchestrator.agent.md'),
    `---\nname: orchestrator\ndescription: ${desc}\n---\n\n${orchestratorBody(skillsDir)}\n\nSkills are in \`${skillsDir}/<skill-name>/SKILL.md\`. Read the SKILL.md before starting a stage.\n`
  );
  ctx.write(
    path.join(ctx.dir, '.github/prompts/orchestrator.prompt.md'),
    readText(path.join(ROOT, 'prompts', 'orchestrator.prompt.md')).split('.claude/skills').join(skillsDir)
  );
  ctx.mergeMcp(path.join(ctx.dir, '.vscode/mcp.json'), 'servers', { type: 'stdio' });
  ctx.log.notes.push(
    'In VS Code, run the prompt with /orchestrator in Copilot Chat (agent mode) or pick the orchestrator agent. The Playwright MCP is configured in .vscode/mcp.json.'
  );
}

function installAntigravity(ctx) {
  const { skillsDir } = TARGETS.antigravity;
  copySkills(ctx, skillsDir);
  ctx.write(
    path.join(ctx.dir, '.agent/rules/prodbridge.md'),
    `${instructions(skillsDir)}\n`
  );
  ctx.write(
    path.join(ctx.dir, '.agent/workflows/orchestrator.md'),
    readText(path.join(ROOT, 'prompts', 'orchestrator.prompt.md')).split('.claude/skills').join(skillsDir)
  );
  ctx.log.notes.push(
    'Antigravity: skills are in .agent/skills, the rule in .agent/rules and the /orchestrator workflow in .agent/workflows. Add the Playwright MCP server (npx @playwright/mcp@latest) from the MCP settings in the Antigravity UI.'
  );
}

function installKiro(ctx) {
  const { skillsDir } = TARGETS.kiro;
  copySkills(ctx, skillsDir);
  ctx.write(
    path.join(ctx.dir, '.kiro/steering/prodbridge.md'),
    `---\ninclusion: always\n---\n\n${instructions(skillsDir)}\n`
  );
  ctx.mergeMcp(path.join(ctx.dir, '.kiro/settings/mcp.json'), 'mcpServers');
  ctx.log.notes.push(
    'Kiro: the steering file tells the agent where each SKILL.md is, so it works even if your Kiro version does not load .kiro/skills natively. The Playwright MCP is in .kiro/settings/mcp.json.'
  );
}

const RUNNERS = {
  claude: installClaude,
  codex: installCodex,
  copilot: installCopilot,
  antigravity: installAntigravity,
  kiro: installKiro,
};

function install({ targets, dir, force = false, dryRun = false }) {
  const ctx = makeCtx({ dir: path.resolve(dir), force, dryRun });
  for (const t of targets) {
    ctx.log.lines.push(`\n[${t}]`);
    RUNNERS[t](ctx);
  }
  ctx.log.notes.push(
    'MCP servers installed: Playwright (needs npx), AWS Knowledge (remote), AWS Core (needs uv/uvx) and Terraform (needs Docker running); remove any you do not need. Skill scripts need Python 3 (and a JDK for java-spring-service). Copy .env.example from the ProdBridge repo to .env for the Jira settings; never commit it.'
  );
  return ctx.log;
}

module.exports = { TARGETS, install, listSkills };
