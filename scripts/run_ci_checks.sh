#!/usr/bin/env bash

# Mirror the CI workflow locally so developers can catch issues before pushing.

set -euo pipefail

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: '$1' is required but not installed." >&2
    exit 1
  fi
}

require_cmd git
require_cmd uv
require_cmd uvx

ROOT_DIR=$(git rev-parse --show-toplevel)
cd "$ROOT_DIR"

HAS_PYTHON=false
if git ls-files '*.py' | grep -q .; then
  HAS_PYTHON=true
fi

HAS_TESTS=false
if find . -type f \( -name 'test_*.py' -o -name '*_test.py' \) | grep -q .; then
  HAS_TESTS=true
fi

run_ruff() {
  echo "==> Running ruff lint"
  uvx --from ruff ruff check

  echo "==> Running ruff format check"
  uvx --from ruff ruff format --check
}

collect_project_files() {
  find . -path './.git' -prune -o -path './.venv' -prune -o -name pyproject.toml -print
}

run_pyright_per_project() {
  local skip_dirs=(".")
  local project_files
  project_files=$(collect_project_files)

  if [ -z "$project_files" ]; then
    echo "No pyproject.toml files found; running pyright once from the repository root."
    uvx --from pyright pyright
    return
  fi

  local project_dir
  local skip

  while IFS= read -r project_file; do
    [ -z "$project_file" ] && continue
    project_dir=$(dirname "$project_file")
    skip=false

    for skip_dir in "${skip_dirs[@]}"; do
      if [ "$project_dir" = "$skip_dir" ]; then
        echo "Skipping $project_file (in skip list)"
        skip=true
        break
      fi
    done
    [ "$skip" = true ] && continue

    echo "::group::pyright ($project_dir)"
    (
      cd "$project_dir"
      uv run --extra dev --with pyright pyright
    )
    echo "::endgroup::"
  done <<< "$project_files"
}

run_pytest_per_project() {
  local skip_dirs=(".")
  local project_files
  project_files=$(collect_project_files)

  if [ -z "$project_files" ]; then
    echo "No pyproject.toml files found; running pytest from the repository root."
    uvx --from pytest pytest
    return
  fi

  local project_dir
  local skip

  while IFS= read -r project_file; do
    [ -z "$project_file" ] && continue
    project_dir=$(dirname "$project_file")
    skip=false

    for skip_dir in "${skip_dirs[@]}"; do
      if [ "$project_dir" = "$skip_dir" ]; then
        echo "Skipping $project_file (in skip list)"
        skip=true
        break
      fi
    done
    [ "$skip" = true ] && continue

    echo "::group::pytest ($project_dir)"
    (
      cd "$project_dir"
      uv run --extra dev --with pytest pytest
    )
    echo "::endgroup::"
  done <<< "$project_files"
}

if [ "$HAS_PYTHON" = true ]; then
  run_ruff

  run_pyright_per_project
else
  echo "Skipping Python-specific checks (no Python files detected)."
fi

if [ "$HAS_TESTS" = true ]; then
  run_pytest_per_project
else
  echo "Skipping pytest (no test files detected)."
fi

echo "All CI checks complete."
