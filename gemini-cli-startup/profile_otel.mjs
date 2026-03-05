#!/usr/bin/env node
// Find which OpenTelemetry package causes the 11-second import delay

import { performance } from 'node:perf_hooks';

async function time(label, fn) {
  const t = performance.now();
  let err;
  try { await fn(); } catch(e) { err = e.message?.slice(0,60); }
  const ms = performance.now() - t;
  const bar = '█'.repeat(Math.min(Math.ceil(ms / 500), 30));
  console.log(`${ms.toFixed(0).padStart(7)}ms  ${bar || '·'}  ${label}${err ? ` [ERR: ${err}]` : ''}`);
  return ms;
}

const OTEL = '/opt/node22/lib/node_modules/@google/gemini-cli/node_modules';
const CORE = `${OTEL}/@google/gemini-cli-core/dist/src`;

console.log('Profiling OpenTelemetry imports (each is incremental after previous)\n');

await time('@opentelemetry/api', () => import(`${OTEL}/@opentelemetry/api/build/src/index.js`));
await time('@opentelemetry/sdk-node', () => import(`${OTEL}/@opentelemetry/sdk-node/build/src/index.js`));
await time('@opentelemetry/sdk-trace-node', () => import(`${OTEL}/@opentelemetry/sdk-trace-node/build/src/index.js`));
await time('@opentelemetry/sdk-logs', () => import(`${OTEL}/@opentelemetry/sdk-logs/build/src/index.js`));
await time('@opentelemetry/sdk-metrics', () => import(`${OTEL}/@opentelemetry/sdk-metrics/build/src/index.js`));
await time('@opentelemetry/instrumentation-http', () => import(`${OTEL}/@opentelemetry/instrumentation-http/build/src/index.js`));
await time('@opentelemetry/exporter-trace-otlp-grpc', () => import(`${OTEL}/@opentelemetry/exporter-trace-otlp-grpc/build/src/index.js`));
await time('@opentelemetry/exporter-logs-otlp-grpc', () => import(`${OTEL}/@opentelemetry/exporter-logs-otlp-grpc/build/src/index.js`));
await time('@opentelemetry/exporter-metrics-otlp-grpc', () => import(`${OTEL}/@opentelemetry/exporter-metrics-otlp-grpc/build/src/index.js`));
await time('@opentelemetry/exporter-trace-otlp-http', () => import(`${OTEL}/@opentelemetry/exporter-trace-otlp-http/build/src/index.js`));
await time('@opentelemetry/exporter-logs-otlp-http', () => import(`${OTEL}/@opentelemetry/exporter-logs-otlp-http/build/src/index.js`));
await time('@opentelemetry/exporter-metrics-otlp-http', () => import(`${OTEL}/@opentelemetry/exporter-metrics-otlp-http/build/src/index.js`));
await time('@grpc/grpc-js (via grpc exporter)', () => import(`${OTEL}/@grpc/grpc-js/build/src/index.js`));
await time('clearcut-logger', () => import(`${CORE}/telemetry/clearcut-logger/clearcut-logger.js`));
await time('gcp-exporters', () => import(`${CORE}/telemetry/gcp-exporters.js`));
await time('google-auth-library', () => import(`${OTEL}/google-auth-library/build/src/index.js`));
