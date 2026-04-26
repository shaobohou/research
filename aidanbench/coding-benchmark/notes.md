# Coding Benchmark: Notes

## Design

MAP-Elites style coding benchmark for claude-sonnet-4-6.

### Feature Space (5 dimensions)
- **Time complexity** (empirical): O(1), O(log n), O(n), O(n log n), O(n²), O(2^n)
- **Space complexity** (empirical): O(1), O(log n), O(n), O(n²)
- **Cyclomatic complexity** (static AST): simple (1-3), moderate (4-7), complex (8+)
- **Built-in reliance** (static AST): none, few (1-3), many (4+)
- **Instruction count** (sys.settrace line events at largest input): tiny (≤50), low (≤500), medium (≤5000), high (5000+)

Instruction count is measured in a separate traced run (does not corrupt timing). `sys.settrace`
adds 5–10x slowdown to the traced run, but since we only care about the *count* (not timing),
the overhead is irrelevant.

### Scoring
Score per problem = number of distinct (time, space, cyclomatic, builtin, instruction) cells
occupied by **correct** solutions.

### Problems
- fibonacci, sort_list, binary_search, two_sum, is_palindrome, factorial

## Status

Implementation complete including 5th bytecode-counting dimension.
Benchmark not yet run.
