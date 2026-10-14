#!/usr/bin/env node
'use strict';

const path = require('path');
const { TARGETS, install, listSkills } = require('../src/installer');

const HELP = `prodbridge-agents - POC-to-production skills for Claude Code, Codex, Copilot, Antigravity and Kiro

Usage:
  npx prodbridge-agents init [--target claude|codex|copilot|antigravity|kiro|all] [--dir <path>] [--force] [--dry-run]
  npx prodbridge-agents list
  npx prodbridge-agents --help

Options:
  --target, -t   Tool to install for (repeatable or comma separated). Default: all
  --dir, -d      Project folder to install into. Default: current folder
  --force, -f    Overwrite existing skill files (managed blocks are always refreshed)
  --dry-run      Show what would be written without writing anything

Targets:
  claude    .claude/skills, .claude/agents, .claude/prompts, .mcp.json
  codex     .agents/skills, AGENTS.md, .codex/config.toml
  copilot   .github/skills, .github/agents, .github/prompts, .github/copilot-instructions.md, .vscode/mcp.json
  antigravity  .agent/skills, .agent/rules, .agent/workflows
  kiro      .kiro/skills, .kiro/steering, .kiro/settings/mcp.json
`;

function parse(argv) {
  const opts = { cmd: null, targets: [], dir: process.cwd(), force: false, dryRun: false };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--help' || a === '-h') opts.cmd = 'help';
    else if (a === '--force' || a === '-f') opts.force = true;
    else if (a === '--dry-run') opts.dryRun = true;
    else if (a === '--target' || a === '-t') opts.targets.push(...String(argv[++i] || '').split(','));
    else if (a.startsWith('--target=')) opts.targets.push(...a.slice(9).split(','));
    else if (a === '--dir' || a === '-d') opts.dir = path.resolve(argv[++i] || '.');
    else if (a.startsWith('--dir=')) opts.dir = path.resolve(a.slice(6));
    else rest.push(a);
  }
  opts.cmd = opts.cmd || rest[0] || 'help';
  return opts;
}

function main() {
  const opts = parse(process.argv.slice(2));
  if (opts.cmd === 'help') return console.log(HELP);
  if (opts.cmd === 'list') {
    for (const s of listSkills()) console.log(`${s.name}\n    ${s.description}`);
    return;
  }
  if (opts.cmd !== 'init') {
    console.error(`Unknown command: ${opts.cmd}\n`);
    console.error(HELP);
    process.exit(1);
  }
  let targets = opts.targets.map((t) => t.trim().toLowerCase()).filter(Boolean);
  if (targets.length === 0 || targets.includes('all')) targets = Object.keys(TARGETS);
  const bad = targets.filter((t) => !TARGETS[t]);
  if (bad.length) {
    console.error(`Unknown target: ${bad.join(', ')}. Choose from: ${Object.keys(TARGETS).join(', ')}, all`);
    process.exit(1);
  }
  const log = install({ targets, dir: opts.dir, force: opts.force, dryRun: opts.dryRun });
  for (const line of log.lines) console.log(line);
  console.log(`\n${opts.dryRun ? 'Dry run: nothing written.' : 'Done.'} ${log.written} written, ${log.skipped} skipped.`);
  for (const note of log.notes) console.log(`\nNote: ${note}`);
}

main();
