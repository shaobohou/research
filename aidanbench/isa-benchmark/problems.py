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
        "io_description": ("IN reads n.  OUT writes fib(n) % 1000000007."),
        "test_cases": [
            ([0], [0]),
            ([1], [1]),
            ([2], [1]),
            ([5], [5]),
            ([7], [13]),
            ([10], [55]),
            ([15], [610]),
            ([20], [6765]),
            ([30], [832040]),
        ],
        "sizes": [100, 500, 1000, 2000, 5000, 10000],
        "encode_fn": lambda n: [n],
    },
}
