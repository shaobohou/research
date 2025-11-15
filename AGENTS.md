# Research and Development Workflow

This workflow applies to all new projects in this repository, including investigations, examples, scaffolding, and experiments.

## Setup

1. **Create a descriptive folder** (e.g., `auth-performance-analysis`, `ngrok-python-agent-example`)
2. **Create `notes.md`** for development logging (recommended for complex projects)

## During Work

**Logging (Recommended):**
- Log progress to `notes.md`: iterations, decisions, challenges, solutions, and learnings
- Track task progress and decisions as you work
- Document what worked and what didn't

**Notes:**
- For simple examples or straightforward implementations, detailed logging may be optional
- For investigations and complex projects, comprehensive notes are valuable

## Final Deliverables

### README.md

**Required sections:**
- **Summary/Overview** - What this is and why it exists
- **Setup/Installation** - How to use or run it
- **Examples** - Code examples using relative paths
- **Documentation** - API, usage, or architecture details

**Additional sections (when applicable):**
- **Objectives** - For investigations or research
- **Key Findings/Conclusions** - For investigations with learnings
- **Next Steps** - Future enhancements or extensions
- **Testing** - How to run tests
- **Troubleshooting** - Common issues and solutions

**Format flexibility:**
- Use the structure that best fits your project type
- Example/scaffolding: Focus on quick start, usage examples, extension guides
- Investigation: Focus on objectives, findings, conclusions, learnings
- Tool/Library: Focus on API reference, usage patterns, examples

### notes.md (Recommended)

**When to include:**
- Complex projects with multiple iterations
- Investigations with significant learnings
- Projects where decision rationale is valuable

**What to log:**
- Development iterations and decisions
- Technical challenges and solutions
- Key learnings and insights
- Alternative approaches tried
- Final state and outcomes

**When optional:**
- Simple, straightforward examples
- Quick scaffolding or boilerplate
- Trivial implementations

## Commit Guidelines

**Include:**
- `README.md` (always required)
- `notes.md` (when it exists)
- Code you wrote
- Tests and configuration files
- `git diff` output from modified repos (save as `.diff` file)
- Binary files < 2MB if necessary

**Exclude:**
- Full cloned repositories
- Unmodified third-party code
- Files > 2MB
- Dependencies or build artifacts (node_modules, venv, __pycache__, etc.)

## Example Structures

### Investigation/Research
```
investigation-name/
├── README.md         # Summary, objectives, findings, conclusions
├── notes.md          # Development log
├── analysis.py       # Code
├── test_analysis.py  # Tests
└── external-repo.diff
```

### Example/Scaffolding
```
example-name/
├── README.md         # Quick start, usage, examples, extensions
├── notes.md          # Optional: development decisions
├── main.py           # Implementation
├── test_main.py      # Tests
└── pyproject.toml    # Configuration
```

### Tool/Library
```
tool-name/
├── README.md         # Overview, installation, API, examples
├── notes.md          # Optional: design decisions
├── src/
│   └── tool/
├── tests/
└── pyproject.toml
```

## Quality Standards

**All projects should:**
- ✅ Have comprehensive README.md
- ✅ Include tests where applicable
- ✅ Use modern Python patterns (type hints, protocols, etc.)
- ✅ Pass linting (ruff, black)
- ✅ Document setup and usage clearly
- ✅ Use relative paths in examples

**Best practices:**
- Prefer simplicity and clarity over complexity
- Document architectural decisions
- Include practical code examples
- Provide next steps or extension ideas
- Follow repository conventions (uv, Python 3.12+, etc.)
