# Development Workflow

Applies to all projects including investigations, examples, scaffolding, and experiments.

## Setup
1. Create a new folder with a descriptive name (e.g., `auth-performance-analysis`)
2. Create `notes.md` for logging progress (optional for simple examples)

## Python Dependencies

For single-file projects, use [uv inline script metadata](https://docs.astral.sh/uv/guides/scripts/) (PEP 723):

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "pandas",
# ]
# ///
```

Run with: `uv run script.py`

Only create `pyproject.toml` or `requirements.txt` for multi-file projects.

## During Work
- **Log continuously** to `notes.md`: what you tried, learned, and what didn't work
- **Track progress**: Update task status as you work through the investigation

## Final Deliverables
Create `README.md` with:
- Summary and objectives
- Key findings and conclusions
- Code examples (use relative paths)
- Next steps if applicable

## Commit Guidelines

**Include:**
- `notes.md` and `README.md`
- Code you wrote
- `git diff` output from modified repos (save as `.diff` file)
- Binary files < 2MB

**Exclude:**
- Full cloned repositories
- Unmodified third-party code
- Files > 2MB
- Dependencies or build artifacts

Example structure:
```
investigation-name/
├── README.md
├── notes.md
├── analysis.py
└── external-repo.diff
```
