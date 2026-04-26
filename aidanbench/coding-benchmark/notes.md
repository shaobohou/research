# Coding Benchmark: Notes

## Design

MAP-Elites style coding benchmark for claude-sonnet-4-6.

### Feature Space (4 dimensions)
- **Time complexity** (instruction count via sys.settrace, fitted): O(1), O(log n), O(n), O(n log n), O(n²), O(2^n)
- **Space complexity** (tracemalloc peak, fitted): O(1), O(log n), O(n), O(n²)
- **Cyclomatic complexity** (static AST): simple (1-3), moderate (4-7), complex (8+)
- **Built-in reliance** (static AST): none, few (1-3), many (4+)

Time complexity uses sys.settrace line-event counts (not wall-clock timing) for a deterministic,
noise-free signal. The tracer runs separately from the timing run, so overhead is irrelevant.

### Scoring
Score per problem = number of distinct (time, space, cyclomatic, builtin) cells
occupied by **correct** solutions.

### Problems
- fibonacci, sort_list, binary_search, two_sum, is_palindrome, factorial

## Status

Implementation complete including 5th bytecode-counting dimension.
Benchmark not yet run.
