#!/usr/bin/env node
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';

function _findClientRepo() {
  const scriptDir = path.dirname(new URL(import.meta.url).pathname);
  const candidates = [
    path.resolve(scriptDir, '../notebooklm-client'),
    path.resolve(scriptDir, '../../notebooklm-client'),
    path.resolve(os.homedir(), '.codex/skills/notebooklm-client'),
    path.resolve(os.homedir(), 'codes/notebooklm-client'),
    path.resolve(os.homedir(), 'notebooklm-client'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, 'dist', 'index.js'))) {
      return c;
    }
  }
  return null;
}

async function _ensureClientRepo() {
  const existing = _findClientRepo();
  if (existing) return existing;

  const target = path.resolve(os.homedir(), '.codex/skills/notebooklm-client');
  if (!fs.existsSync(path.join(target, '.git'))) {
    const { execSync } = await import('child_process');
    try {
      execSync(`git clone https://github.com/icebear0828/notebooklm-client.git "${target}"`, { stdio: 'pipe', timeout: 120000 });
    } catch {
      return null;
    }
  }
  if (!fs.existsSync(path.join(target, 'dist', 'index.js'))) {
    const { execSync } = await import('child_process');
    try {
      execSync('npm install', { cwd: target, stdio: 'pipe', timeout: 120000 });
      execSync('npm run build', { cwd: target, stdio: 'pipe', timeout: 120000 });
    } catch {
      return null;
    }
  }
  return fs.existsSync(path.join(target, 'dist', 'index.js')) ? target : null;
}

async function loadNotebookClient() {
  try {
    return await import('notebooklm-client');
  } catch {}

  const explicitEntry = process.env.NOTEBOOKLM_CLIENT_INDEX;
  if (explicitEntry) {
    return import(pathToFileURL(path.resolve(explicitEntry)).href);
  }

  const explicitRoot = process.env.NOTEBOOKLM_CLIENT_ROOT;
  if (explicitRoot) {
    const entry = path.resolve(explicitRoot, 'dist', 'index.js');
    return import(pathToFileURL(entry).href);
  }

  const repo = await _ensureClientRepo();
  if (repo) {
    const entry = path.resolve(repo, 'dist', 'index.js');
    return import(pathToFileURL(entry).href);
  }

  throw new Error(
    'Cannot load notebooklm-client. Install it as a package, set NOTEBOOKLM_CLIENT_ROOT / NOTEBOOKLM_CLIENT_INDEX, or ensure git and npm are available for auto-clone.',
  );
}

function resolveProxy() {
  return process.env.HTTPS_PROXY
    || process.env.https_proxy
    || process.env.ALL_PROXY
    || process.env.all_proxy
    || undefined;
}

async function main() {
  const title = process.argv.slice(2).join(' ').trim();
  if (!title) {
    console.error('Usage: node scripts/notebooklm_create.mjs <title>');
    process.exit(1);
  }

  const { NotebookClient } = await loadNotebookClient();
  const client = new NotebookClient();
  try {
    await client.connect({ transport: 'auto', proxy: resolveProxy() });
    const result = await client.createNotebook();
    if (title) {
      try {
        await client.renameNotebook(result.notebookId, title);
      } catch {
        // Notebook creation is the critical step; title rename is best-effort.
      }
    }
    console.log(JSON.stringify({ notebookId: result.notebookId, title }, null, 2));
  } finally {
    await client.disconnect();
  }
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
