#!/usr/bin/env node
// Instruments Gemini CLI startup phases by monkey-patching key modules
// Run with: node profile_startup.mjs

import { performance } from 'node:perf_hooks';
import { spawn } from 'node:child_process';
import { resolve } from 'node:path';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';

const GEMINI_DIST = '/opt/node22/lib/node_modules/@google/gemini-cli/dist';

// ── Phase timers ──────────────────────────────────────────────────────────────
const phases = [];
function mark(name) {
  phases.push({ name, t: performance.now() });
  process.stderr.write(`[+${(performance.now()).toFixed(0).padStart(6)}ms] ${name}\n`);
}

mark('script_start');

// ── Instrument by timing each import ─────────────────────────────────────────
const t0 = performance.now();

// Time how long it takes to just import the main gemini module
mark('before_import_gemini_core');

let coreModule;
try {
  coreModule = await import(`${GEMINI_DIST}/src/gemini.js`);
  mark('after_import_gemini_core');
} catch (e) {
  mark(`import_failed: ${e.message.slice(0, 80)}`);
}

// ── Report ────────────────────────────────────────────────────────────────────
console.log('\n=== Startup Phase Breakdown ===');
for (let i = 1; i < phases.length; i++) {
  const delta = phases[i].t - phases[i - 1].t;
  console.log(`  ${phases[i].name.padEnd(40)} ${delta.toFixed(1).padStart(8)}ms`);
}
const total = phases[phases.length - 1].t - phases[0].t;
console.log(`  ${'TOTAL'.padEnd(40)} ${total.toFixed(1).padStart(8)}ms`);
