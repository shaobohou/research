#!/usr/bin/env node
// Times each top-level import in the gemini bundle to find what's slow

import { performance } from 'node:perf_hooks';

const DIST = '/opt/node22/lib/node_modules/@google/gemini-cli/dist/src';
const CORE = '/opt/node22/lib/node_modules/@google/gemini-cli/node_modules/@google/gemini-cli-core/dist/src';

async function time(label, fn) {
  const t = performance.now();
  let result, err;
  try { result = await fn(); } catch(e) { err = e.message?.slice(0,60); }
  const ms = performance.now() - t;
  console.log(`${ms.toFixed(1).padStart(8)}ms  ${label}${err ? ` [ERR: ${err}]` : ''}`);
  return result;
}

console.log('Timing individual module imports...\n');

await time('node:perf_hooks (baseline)', () => import('node:perf_hooks'));
await time('node:fs', () => import('node:fs'));
await time('node:child_process', () => import('node:child_process'));
await time('react', () => import('react'));
await time('@google/gemini-cli-core (full)', () => import(`${CORE}/index.js`));
await time('config/settings', () => import(`${DIST}/config/settings.js`));
await time('config/config', () => import(`${DIST}/config/config.js`));
await time('utils/readStdin', () => import(`${DIST}/utils/readStdin.js`));
await time('utils/relaunch', () => import(`${DIST}/utils/relaunch.js`));
await time('utils/cleanup', () => import(`${DIST}/utils/cleanup.js`));
await time('config/auth', () => import(`${DIST}/config/auth.js`));
await time('config/sandboxConfig', () => import(`${DIST}/config/sandboxConfig.js`));
await time('validateNonInterActiveAuth', () => import(`${DIST}/validateNonInterActiveAuth.js`));

console.log('\nDone (note: repeated imports are cached, ordering matters)');
