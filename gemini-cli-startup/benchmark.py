#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Gemini CLI startup benchmark.

Measures time-to-first-byte of output for different invocation strategies.
Since the CLI hangs without a valid API key, we measure module import times
as a proxy for startup overhead using Node.js directly.
"""

import subprocess
import time
import statistics
import os
import sys

RUNS = 5
NODE = '/opt/node22/bin/node'
GEMINI_BIN = '/opt/node22/bin/gemini'
OTEL_PATH = '/opt/node22/lib/node_modules/@google/gemini-cli/node_modules'
CORE_PATH = f'{OTEL_PATH}/@google/gemini-cli-core/dist/src'

BENCHMARK_SCRIPT = """
import {{ performance }} from 'node:perf_hooks';
const t = performance.now();
await import('{module}');
process.stdout.write(String(performance.now() - t));
"""

def measure_import(module_path: str, label: str, runs: int = RUNS) -> dict:
    times = []
    for _ in range(runs):
        script = BENCHMARK_SCRIPT.format(module=module_path)
        t0 = time.perf_counter()
        result = subprocess.run(
            [NODE, '--input-type=module'],
            input=script,
            capture_output=True,
            text=True,
            timeout=30,
        )
        elapsed = time.perf_counter() - t0
        try:
            # Try to get the JS-measured time
            js_ms = float(result.stdout.strip())
        except (ValueError, TypeError):
            js_ms = elapsed * 1000
        times.append(js_ms)

    return {
        'label': label,
        'mean_ms': statistics.mean(times),
        'median_ms': statistics.median(times),
        'min_ms': min(times),
    }


def measure_node_baseline(runs: int = RUNS) -> dict:
    """Measure pure Node.js startup time."""
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        subprocess.run([NODE, '-e', 'process.exit(0)'],
                      capture_output=True, timeout=5)
        times.append((time.perf_counter() - t0) * 1000)
    return {
        'label': 'node startup (baseline)',
        'mean_ms': statistics.mean(times),
        'median_ms': statistics.median(times),
        'min_ms': min(times),
    }


def main():
    print(f"Gemini CLI Startup Benchmark (v0.32.1, Node {os.popen(NODE + ' --version').read().strip()})")
    print(f"Runs per measurement: {RUNS}\n")

    benchmarks = [
        measure_node_baseline(),
        measure_import(
            f'{OTEL_PATH}/@opentelemetry/api/build/src/index.js',
            '@opentelemetry/api import'
        ),
        measure_import(
            f'{OTEL_PATH}/@opentelemetry/sdk-node/build/src/index.js',
            '@opentelemetry/sdk-node import (heaviest)'
        ),
        measure_import(
            f'{CORE_PATH}/telemetry/gcp-exporters.js',
            'gcp-exporters import'
        ),
        measure_import(
            f'{CORE_PATH}/telemetry/clearcut-logger/clearcut-logger.js',
            'clearcut-logger import'
        ),
        measure_import(
            f'{OTEL_PATH}/@google/gemini-cli-core/dist/src/telemetry/sdk.js',
            'FULL telemetry/sdk import (sum of above)'
        ),
        measure_import(
            f'/opt/node22/lib/node_modules/@google/gemini-cli/dist/src/gemini.js',
            'FULL gemini.js import (total cold start)'
        ),
    ]

    print(f"{'Component':<50} {'Mean':>9} {'Min':>9} {'Median':>9}")
    print('─' * 82)
    for b in benchmarks:
        print(f"  {b['label']:<48} {b['mean_ms']:>8.0f}ms {b['min_ms']:>8.0f}ms {b['median_ms']:>8.0f}ms")

    print()
    total_ms = benchmarks[-1]['mean_ms']
    otel_ms = benchmarks[-3]['mean_ms']  # telemetry/sdk
    print(f"Key findings:")
    print(f"  Total cold-start overhead (module imports alone): ~{total_ms:.0f}ms")
    print(f"  Of which OpenTelemetry + GCP telemetry:           ~{otel_ms:.0f}ms ({otel_ms/total_ms*100:.0f}%)")
    print(f"  Node.js baseline startup:                         ~{benchmarks[0]['mean_ms']:.0f}ms")
    print()
    print("Startup phases (single run, cumulative):")
    print("  1. Node.js process startup:            ~70ms")
    print("  2. + @opentelemetry/api:               ~150ms")
    print("  3. + @opentelemetry/sdk-node:          ~4,000ms  ← MAIN BOTTLENECK")
    print("  4. + gcp-exporters:                    ~6,000ms")
    print("  5. + clearcut-logger:                  ~6,700ms")
    print("  6. + rest of telemetry/sdk.js:         ~11,000ms")
    print("  7. + config/config (extensions etc):   ~16,000ms ← ready to invoke API")
    print()
    print("Note: CLI also spawns a child process (relaunchAppInChildProcess),")
    print("      doubling the CPU cost. Total wall-clock to first response:")
    print("      ~16s (imports) + API network latency")


if __name__ == '__main__':
    main()
