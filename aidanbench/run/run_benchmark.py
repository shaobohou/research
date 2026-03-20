"""
Runner script for AidanBench using Anthropic API.
Tests claude-sonnet-4-6 on all 61 questions.
"""
import sys
import os

# Add our custom models.py directory first (so it overrides AidanBench's models.py)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Add AidanBench benchmark directory to path
AIDANBENCH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'AidanBench', 'benchmark')
sys.path.insert(1, os.path.abspath(AIDANBENCH_DIR))

# Verify our models module is used
import models
print(f"Using models from: {models.__file__}")

# Quick smoke test
print("Testing Anthropic API connection...")
resp = models.chat_with_model("Say 'API OK' and nothing else.", model="claude-sonnet-4-6", max_tokens=10)
print(f"API test: {resp}")

print("Testing embedding...")
e = models.embed("test sentence")
print(f"Embedding dim: {len(e)}")

# Now run the benchmark
import main as _main_module
from concurrent.futures import ThreadPoolExecutor, as_completed

# Patch max_workers to limit parallelism and avoid rate limits
_orig_multithreaded = _main_module._run_multithreaded
def _patched_multithreaded(model_params, chain_of_thought, use_llm, results, results_file, thresholds):
    from main import _process_question, _can_skip_question, _save_results
    from colorama import Fore, Style
    with ThreadPoolExecutor(max_workers=8) as executor:
        all_futures = []
        active_models = []
        for model, model_tasks in model_params.items():
            if all(_can_skip_question(results, question, model, temp, use_llm, thresholds)
                   for question, model, temp in model_tasks):
                print(f"Skipping all questions for {model} - already completed")
                continue
            active_models.append(model)
            model_futures = [
                executor.submit(_process_question, question, model, temp,
                                chain_of_thought, use_llm, results, thresholds)
                for question, model, temp in model_tasks
            ]
            all_futures.extend(model_futures)
        completed = 0
        total = len(all_futures)
        if total == 0:
            print("No tasks to process - all models completed")
            return
        print(f"Processing {total} tasks across {len(active_models)} models (8 workers)")
        for future in as_completed(all_futures):
            try:
                future.result()
                completed += 1
                if completed % 5 == 0:
                    print(f"Completed {completed}/{total} tasks")
            except Exception as e:
                print(f"{Fore.RED}Error during benchmark: {e}{Style.RESET_ALL}")
                completed += 1
            if completed % 20 == 0 or completed == total:
                _save_results(results, results_file)

_main_module._run_multithreaded = _patched_multithreaded
from main import run_benchmark

RESULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results.json')

print("\n" + "="*60)
print("Starting AidanBench on claude-sonnet-4-6")
print("="*60 + "\n")

run_benchmark(
    model_names=["anthropic/claude-sonnet-4"],  # mapped to claude-sonnet-4-6
    temperatures=[0.7],
    chain_of_thought=False,
    use_llm=False,
    multithreaded=True,   # parallel to speed things up
    num_questions=None,   # all 61 questions
    results_file=RESULTS_FILE,
    thresholds={
        'coherence_score': 15,
        'embedding_dissimilarity_score': 0.15,
        'llm_dissimilarity_score': 0.15
    }
)

print(f"\nResults saved to: {RESULTS_FILE}")
