# Coding Benchmark: Notes

## Design

MAP-Elites style coding benchmark for claude-sonnet-4-6.

### Feature Space (4 dimensions)
- **Time complexity** (empirical): O(1), O(log n), O(n), O(n log n), O(n²), O(2^n)
- **Space complexity** (empirical): O(1), O(log n), O(n), O(n²)
- **Cyclomatic complexity** (static AST): simple (1-3), moderate (4-7), complex (8+)
- **Built-in reliance** (static AST): none, few (1-3), many (4+)

### Scoring
Score per problem = number of distinct (time, space, cyclomatic, builtin) cells
occupied by **correct** solutions.

### Problems
- fibonacci, sort_list, binary_search, two_sum, is_palindrome, factorial

## Status

Implementation complete. Benchmark not yet run — paused to reconsider
instrumentation approach. Considering CPython bytecode counting (sys.monitoring)
instead of wall-clock timing for more reliable complexity classification.
