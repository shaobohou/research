"""
ISA benchmark problem definitions.

Each problem:
  description    — plain-English problem statement shown to the model
  io_description — how the input tape is structured and what to output
  test_cases     — list of (input_tape: list[int], expected_outputs: list[int])
  sizes          — list of ints for empirical complexity measurement
  encode_fn      — callable(n) -> list[int]: builds input tape for size n

Fibonacci
  Input tape : [n]
  Output tape: [fib(n) % (10^9+7)]
  fib(0)=0, fib(1)=1, fib(2)=1, fib(7)=13

Binary search
  Input tape : [array_len, arr[0], arr[1], ..., arr[n-1], target]
  Output tape: [index]  (0-based), or [-1] if not found
"""

MOD = 10**9 + 7


def _ref_fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, (a + b) % MOD
    return a


PROBLEMS = {
    "fibonacci": {
        "description": (
            "Given a non-negative integer n (read from input), compute the nth Fibonacci "
            "number modulo 10^9+7 (where 10^9+7 = 1000000007) and write it to output.\n"
            "fib(0)=0, fib(1)=1, fib(2)=1, fib(7)=13, fib(10)=55.\n"
            "Apply the modulus at each addition step to keep values in 32-bit range."
        ),
        "io_description": (
            "IN reads n.  OUT writes fib(n) % 1000000007."
        ),
        "test_cases": [
            ([0],  [0]),
            ([1],  [1]),
            ([2],  [1]),
            ([5],  [5]),
            ([7],  [13]),
            ([10], [55]),
            ([15], [610]),
            ([20], [6765]),
            ([30], [832040]),
        ],
        "sizes":     [100, 500, 1000, 2000, 5000, 10000],
        "encode_fn": lambda n: [n],
    },

    "binary_search": {
        "description": (
            "A sorted array of integers is provided on the input tape followed by a target "
            "integer.  Find the index (0-based) of the target in the array.  "
            "Output that index, or -1 if the target is not present.\n"
            "Use binary search — the input tape format is:\n"
            "  n  arr[0]  arr[1]  ...  arr[n-1]  target"
        ),
        "io_description": (
            "IN reads: n (array length), then n sorted integers, then target.\n"
            "OUT writes the 0-based index of target in the array, or -1 if absent."
        ),
        "test_cases": [
            ([5, 1, 3, 5, 7, 9,  5],  [2]),   # mid element
            ([5, 1, 3, 5, 7, 9,  1],  [0]),   # first
            ([5, 1, 3, 5, 7, 9,  9],  [4]),   # last
            ([5, 1, 3, 5, 7, 9,  4],  [-1]),  # missing
            ([1, 7,              7],  [0]),   # single-element found
            ([1, 7,              8],  [-1]),  # single-element missing
            ([4, 2, 4, 6, 8,     6],  [2]),   # even-length, middle
        ],
        # encode_fn: array [0,2,4,...,2n-2] (n elements), target = 2*(n//2) at index n//2
        "sizes":     [16, 64, 256, 1024, 4096],
        "encode_fn": lambda n: [n] + list(range(0, 2 * n, 2)) + [2 * (n // 2)],
    },
}
