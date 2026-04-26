import random

# Each problem defines:
#   description: shown to the model
#   signature:   function signature hint
#   test_cases:  list of (input, expected) for correctness check
#                input is a tuple of args, or a single value
#   size_input:  callable(n) -> args tuple for empirical complexity measurement
#   reference:   correct implementation for generating expected outputs

def _ref_fibonacci(n):
    MOD = 10**9 + 7
    a, b = 0, 1
    for _ in range(n):
        a, b = b, (a + b) % MOD
    return a

def _ref_sort(lst):
    return sorted(lst)

def _ref_binary_search(arr, target):
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1

def _ref_two_sum(nums, target):
    seen = {}
    for i, n in enumerate(nums):
        if target - n in seen:
            return [seen[target - n], i]
        seen[n] = i
    return []

def _ref_is_palindrome(s):
    return s == s[::-1]

def _ref_factorial(n):
    r = 1
    for i in range(2, n + 1):
        r *= i
    return r


PROBLEMS = {
    "fibonacci": {
        "description": (
            "Given a non-negative integer n, return the nth Fibonacci number modulo 10^9+7 "
            "(0-indexed: fib(0)=0, fib(1)=1, fib(2)=1, fib(7)=13, fib(50)=586268941). "
            "Using a modulus keeps values bounded so you must apply % (10**9+7) at each step."
        ),
        "signature": "solve(n: int) -> int",
        "test_cases": [
            ((0,), 0), ((1,), 1), ((2,), 1), ((5,), 5),
            ((7,), 13), ((10,), 55), ((15,), 610),
            ((50,), 586268941), ((100,), 687995182),
        ],
        "size_input": lambda n: (n,),
        "sizes": [100, 500, 2000, 10000, 50000, 200000],
        "timeout_per_run": 2.0,
    },
    "sort_list": {
        "description": (
            "Given a list of integers, return a new list sorted in ascending order."
        ),
        "signature": "solve(lst: list) -> list",
        "test_cases": [
            (([3, 1, 2],), [1, 2, 3]),
            (([],), []),
            (([1],), [1]),
            (([5, 4, 3, 2, 1],), [1, 2, 3, 4, 5]),
            (([2, 2, 1],), [1, 2, 2]),
        ],
        "size_input": lambda n: ([random.randint(0, 10000) for _ in range(n)],),
        "sizes": [100, 200, 400, 800, 1600, 3200],
        "timeout_per_run": 5.0,
    },
    "binary_search": {
        "description": (
            "Given a sorted list of integers arr and a target integer, "
            "return the index of target in arr, or -1 if not found."
        ),
        "signature": "solve(arr: list, target: int) -> int",
        "test_cases": [
            (([1, 3, 5, 7, 9], 5), 2),
            (([1, 3, 5, 7, 9], 1), 0),
            (([1, 3, 5, 7, 9], 9), 4),
            (([1, 3, 5, 7, 9], 4), -1),
            (([1], 1), 0),
            (([1], 2), -1),
        ],
        "size_input": lambda n: (list(range(0, n * 2, 2)), n),  # target always present
        "sizes": [100, 500, 1000, 5000, 10000, 50000],
        "timeout_per_run": 2.0,
    },
    "two_sum": {
        "description": (
            "Given a list of integers nums and an integer target, return the indices "
            "[i, j] (i < j) of the two numbers that add up to target. "
            "There is exactly one solution."
        ),
        "signature": "solve(nums: list, target: int) -> list",
        "test_cases": [
            (([2, 7, 11, 15], 9), [0, 1]),
            (([3, 2, 4], 6), [1, 2]),
            (([1, 5, 3, 2], 5), [2, 3]),
            (([0, 4, 3, 0], 0), [0, 3]),
        ],
        "size_input": lambda n: _two_sum_input(n),
        "sizes": [100, 200, 400, 800, 1600, 3200],
        "timeout_per_run": 5.0,
    },
    "is_palindrome": {
        "description": (
            "Given a string s, return True if it reads the same forwards and backwards, "
            "False otherwise."
        ),
        "signature": "solve(s: str) -> bool",
        "test_cases": [
            (("racecar",), True),
            (("hello",), False),
            (("",), True),
            (("a",), True),
            (("abba",), True),
            (("abca",), False),
        ],
        "size_input": lambda n: (_palindrome_input(n),),
        "sizes": [100, 500, 1000, 5000, 10000, 50000],
        "timeout_per_run": 2.0,
    },
    "factorial": {
        "description": (
            "Given a non-negative integer n, return n! (n factorial). "
            "factorial(0) = 1, factorial(5) = 120."
        ),
        "signature": "solve(n: int) -> int",
        "test_cases": [
            ((0,), 1), ((1,), 1), ((5,), 120),
            ((10,), 3628800), ((15,), 1307674368000),
        ],
        "size_input": lambda n: (n,),
        "sizes": [50, 100, 200, 400, 800, 1000],
        "timeout_per_run": 2.0,
    },
}


def _two_sum_input(n):
    nums = [random.randint(1, 1000) for _ in range(n)]
    i, j = random.sample(range(n), 2)
    if i > j:
        i, j = j, i
    target = nums[i] + nums[j]
    # ensure uniqueness: remove any other pair that sums to target
    for k in range(n):
        for l in range(k + 1, n):
            if (k, l) != (i, j) and nums[k] + nums[l] == target:
                nums[l] = random.randint(1001, 2000)
    return (nums, target)


def _palindrome_input(n):
    half = "".join(random.choices("abcdefgh", k=n // 2))
    return half + half[::-1]
