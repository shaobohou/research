#!/usr/bin/env node
// Drill into gemini-cli-core sub-modules to find which one is slow

import { performance } from 'node:perf_hooks';

const CORE = '/opt/node22/lib/node_modules/@google/gemini-cli/node_modules/@google/gemini-cli-core/dist/src';

async function time(label, fn) {
  const t = performance.now();
  let err;
  try { await fn(); } catch(e) { err = e.message?.slice(0,80); }
  const ms = performance.now() - t;
  const bar = '█'.repeat(Math.min(Math.floor(ms / 200), 50));
  console.log(`${ms.toFixed(0).padStart(7)}ms  ${bar}  ${label}${err ? ` [ERR: ${err}]` : ''}`);
  return ms;
}

// List key sub-modules of gemini-cli-core
const modules = [
  'telemetry/sdk',
  'telemetry/index',
  'code_assist/telemetry',
  'tools/index',
  'tools/toolRegistry',
  'tools/read-file',
  'tools/shell',
  'tools/mcp-client/mcpClient',
  'config/index',
  'config/config',
  'llmInteraction/llm-interaction',
  'services/fileDiscovery',
  'memory/memory',
  'extensions/index',
];

console.log('Drilling into @google/gemini-cli-core sub-modules\n');
const results = [];
for (const mod of modules) {
  const ms = await time(mod, () => import(`${CORE}/${mod}.js`));
  results.push({ mod, ms });
}

console.log('\n--- Top 5 slowest (incremental load time) ---');
results.sort((a, b) => b.ms - a.ms).slice(0, 5).forEach(r => {
  console.log(`  ${r.ms.toFixed(0).padStart(7)}ms  ${r.mod}`);
});
