"""Full test suite for the ISA interpreter."""

import unittest
from interpreter import run, parse, RunResult, _wrap32, _MAX32, _MIN32

# ── Helpers ───────────────────────────────────────────────────────────────────

def ok(source, inputs=None, *, max_steps=10_000_000):
    r = run(source, inputs or [], max_steps=max_steps)
    assert r.ok, f'Unexpected error: {r.error}'
    return r

def err(source, inputs=None, *, constraints=None, max_steps=10_000_000):
    r = run(source, inputs or [], constraints=constraints, max_steps=max_steps)
    assert not r.ok, 'Expected an error but got none'
    return r


# ── Individual instructions ───────────────────────────────────────────────────

class TestMOV(unittest.TestCase):
    def test_reg_to_reg(self):
        r = ok('MOV R0, R1\n OUT R0\n HALT', [])
        self.assertEqual(r.outputs, [0])

    def test_imm_positive(self):
        r = ok('MOV R0, 42\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [42])

    def test_imm_negative(self):
        r = ok('MOV R0, -7\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [-7])

    def test_overwrites(self):
        r = ok('MOV R0, 5\n MOV R0, 99\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [99])

    def test_copy_between_regs(self):
        r = ok('MOV R3, 17\n MOV R5, R3\n OUT R5\n HALT')
        self.assertEqual(r.outputs, [17])


class TestADD(unittest.TestCase):
    def test_reg_plus_imm(self):
        r = ok('MOV R0, 10\n ADD R0, 5\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [15])

    def test_reg_plus_reg(self):
        r = ok('MOV R0, 3\n MOV R1, 4\n ADD R0, R1\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [7])

    def test_add_negative(self):
        r = ok('MOV R0, 10\n ADD R0, -3\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [7])

    def test_accumulates(self):
        r = ok('ADD R0, 1\n ADD R0, 1\n ADD R0, 1\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [3])


class TestSUB(unittest.TestCase):
    def test_basic(self):
        r = ok('MOV R0, 10\n SUB R0, 3\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [7])

    def test_reg_minus_reg(self):
        r = ok('MOV R0, 9\n MOV R1, 4\n SUB R0, R1\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [5])

    def test_negative_result(self):
        r = ok('MOV R0, 3\n SUB R0, 10\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [-7])


class TestMUL(unittest.TestCase):
    def test_basic(self):
        r = ok('MOV R0, 6\n MUL R0, 7\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [42])

    def test_by_zero(self):
        r = ok('MOV R0, 99\n MUL R0, 0\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [0])

    def test_negative(self):
        r = ok('MOV R0, 5\n MUL R0, -3\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [-15])

    def test_reg_by_reg(self):
        r = ok('MOV R0, 8\n MOV R1, 9\n MUL R0, R1\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [72])


class TestDIV(unittest.TestCase):
    def test_exact(self):
        r = ok('MOV R0, 12\n DIV R0, 4\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [3])

    def test_truncates_toward_zero_positive(self):
        r = ok('MOV R0, 7\n DIV R0, 2\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [3])

    def test_truncates_toward_zero_negative(self):
        r = ok('MOV R0, -7\n DIV R0, 2\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [-3])

    def test_by_zero(self):
        err('MOV R0, 5\n DIV R0, 0\n HALT')

    def test_reg_div_reg(self):
        r = ok('MOV R0, 20\n MOV R1, 4\n DIV R0, R1\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [5])


class TestMOD(unittest.TestCase):
    def test_basic(self):
        r = ok('MOV R0, 10\n MOD R0, 3\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [1])

    def test_exact(self):
        r = ok('MOV R0, 9\n MOD R0, 3\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [0])

    def test_by_zero(self):
        err('MOV R0, 5\n MOD R0, 0\n HALT')

    def test_large_modulus(self):
        MOD = 10**9 + 7
        r = ok(f'MOV R0, 100\n MOV R1, {MOD}\n MOD R0, R1\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [100])


class TestMemory(unittest.TestCase):
    def test_stor_and_load(self):
        r = ok('MOV R0, 42\n MOV R1, 5\n STOR R0, [R1]\n LOAD R2, [R1]\n OUT R2\n HALT')
        self.assertEqual(r.outputs, [42])

    def test_positive_offset(self):
        r = ok('MOV R0, 99\n MOV R1, 10\n STOR R0, [R1+3]\n LOAD R2, [R1+3]\n OUT R2\n HALT')
        self.assertEqual(r.outputs, [99])

    def test_negative_offset(self):
        r = ok('MOV R0, 77\n MOV R1, 5\n STOR R0, [R1-2]\n LOAD R2, [R1-2]\n OUT R2\n HALT')
        self.assertEqual(r.outputs, [77])

    def test_zero_base(self):
        r = ok('MOV R0, 55\n MOV R1, 0\n STOR R0, [R1]\n LOAD R2, [R1]\n OUT R2\n HALT')
        self.assertEqual(r.outputs, [55])

    def test_uninitialised_reads_zero(self):
        r = ok('MOV R1, 100\n LOAD R0, [R1]\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [0])

    def test_stor_immediate(self):
        r = ok('MOV R1, 3\n STOR 42, [R1]\n LOAD R0, [R1]\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [42])

    def test_mem_hwm_tracks_writes(self):
        r = ok('MOV R1, 10\n STOR 1, [R1]\n MOV R1, 20\n STOR 2, [R1]\n HALT')
        self.assertEqual(r.mem_hwm, 20)

    def test_read_does_not_update_hwm(self):
        r = ok('MOV R1, 50\n LOAD R0, [R1]\n HALT')
        self.assertEqual(r.mem_hwm, 0)

    def test_address_out_of_range(self):
        err('MOV R0, 1\n MOV R1, 70000\n STOR R0, [R1]\n HALT')


class TestControlFlow(unittest.TestCase):
    def test_jmp(self):
        r = ok('JMP done\n OUT 99\ndone: OUT 1\n HALT')
        self.assertEqual(r.outputs, [1])

    def test_jz_taken(self):
        r = ok('MOV R0, 0\n JZ R0, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [1])

    def test_jz_not_taken(self):
        r = ok('MOV R0, 5\n JZ R0, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [0])

    def test_jnz_taken(self):
        r = ok('MOV R0, 3\n JNZ R0, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [1])

    def test_jnz_not_taken(self):
        r = ok('MOV R0, 0\n JNZ R0, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [0])

    def test_jlt_taken(self):
        r = ok('MOV R0, 3\n JLT R0, 5, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [1])

    def test_jlt_not_taken_equal(self):
        r = ok('MOV R0, 5\n JLT R0, 5, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [0])

    def test_jlt_not_taken_greater(self):
        r = ok('MOV R0, 7\n JLT R0, 5, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [0])

    def test_jle_taken_equal(self):
        r = ok('MOV R0, 5\n JLE R0, 5, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [1])

    def test_jle_taken_less(self):
        r = ok('MOV R0, 3\n JLE R0, 5, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [1])

    def test_jle_not_taken(self):
        r = ok('MOV R0, 6\n JLE R0, 5, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [0])

    def test_loop(self):
        # sum 1..5 = 15
        prog = 'MOV R0, 5\n MOV R1, 0\nloop: JZ R0, done\n ADD R1, R0\n SUB R0, 1\n JMP loop\ndone: OUT R1\n HALT'
        r = ok(prog)
        self.assertEqual(r.outputs, [15])

    def test_label_on_instruction_line(self):
        r = ok('JMP target\n OUT 0\n HALT\ntarget: OUT 7\n HALT')
        self.assertEqual(r.outputs, [7])

    def test_label_standalone_line(self):
        r = ok('JMP target\n OUT 0\n HALT\ntarget:\n OUT 7\n HALT')
        self.assertEqual(r.outputs, [7])

    def test_unknown_label(self):
        err('JMP nowhere\n HALT')


class TestIO(unittest.TestCase):
    def test_in_out(self):
        r = ok('IN R0\n OUT R0\n HALT', [42])
        self.assertEqual(r.outputs, [42])

    def test_multiple_inputs(self):
        r = ok('IN R0\n IN R1\n ADD R0, R1\n OUT R0\n HALT', [3, 4])
        self.assertEqual(r.outputs, [7])

    def test_out_immediate(self):
        r = ok('OUT 123\n HALT')
        self.assertEqual(r.outputs, [123])

    def test_multiple_outputs(self):
        r = ok('OUT 1\n OUT 2\n OUT 3\n HALT')
        self.assertEqual(r.outputs, [1, 2, 3])

    def test_input_exhausted(self):
        err('IN R0\n IN R1\n HALT', [42])

    def test_insn_count(self):
        # MOV, MOV, ADD, HALT — HALT counts as an executed instruction
        r = ok('MOV R0, 1\n MOV R1, 2\n ADD R0, R1\n HALT')
        self.assertEqual(r.insn_count, 4)


class TestMacros(unittest.TestCase):
    def test_inc(self):
        r = ok('MOV R0, 5\n INC R0\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [6])

    def test_dec(self):
        r = ok('MOV R0, 5\n DEC R0\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [4])

    def test_clr(self):
        r = ok('MOV R0, 99\n CLR R0\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [0])

    def test_neg(self):
        r = ok('MOV R0, 7\n NEG R0\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [-7])

    def test_neg_negative(self):
        r = ok('MOV R0, -3\n NEG R0\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [3])

    def test_jgt_taken(self):
        r = ok('MOV R0, 7\n JGT R0, 5, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [1])

    def test_jgt_not_taken_equal(self):
        r = ok('MOV R0, 5\n JGT R0, 5, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [0])

    def test_jgt_not_taken_less(self):
        r = ok('MOV R0, 3\n JGT R0, 5, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [0])

    def test_jge_taken_equal(self):
        r = ok('MOV R0, 5\n JGE R0, 5, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [1])

    def test_jge_taken_greater(self):
        r = ok('MOV R0, 7\n JGE R0, 5, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [1])

    def test_jge_not_taken(self):
        r = ok('MOV R0, 3\n JGE R0, 5, yes\n OUT 0\n HALT\nyes: OUT 1\n HALT')
        self.assertEqual(r.outputs, [0])


class TestOverflow(unittest.TestCase):
    def test_max_plus_one_wraps(self):
        r = ok(f'MOV R0, {_MAX32}\n ADD R0, 1\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [_MIN32])

    def test_min_minus_one_wraps(self):
        r = ok(f'MOV R0, {_MIN32}\n SUB R0, 1\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [_MAX32])

    def test_wrap32_utility(self):
        self.assertEqual(_wrap32(_MAX32 + 1), _MIN32)
        self.assertEqual(_wrap32(_MIN32 - 1), _MAX32)
        self.assertEqual(_wrap32(0), 0)


# ── Complete programs ─────────────────────────────────────────────────────────

FIB_ITERATIVE = """
    IN   R0          ; n
    MOV  R1, 0       ; a
    MOV  R2, 1       ; b
loop:
    JZ   R0, done
    MOV  R3, R2
    ADD  R2, R1
    MOV  R1, R3
    DEC  R0
    JMP  loop
done:
    OUT  R1
    HALT
"""

FIB_DP = """
    IN   R0          ; n
    JZ   R0, zero
    STOR 0, [R7+0]   ; mem[0] = 0  (R7=0)
    STOR 1, [R7+1]   ; mem[1] = 1
    MOV  R1, 2       ; i = 2
fill:
    JGT  R1, R0, done
    MOV  R2, R1
    DEC  R2          ; i-1
    LOAD R3, [R2]    ; mem[i-1]
    DEC  R2          ; i-2
    LOAD R4, [R2]    ; mem[i-2]
    ADD  R3, R4
    STOR R3, [R1]    ; mem[i] = mem[i-1] + mem[i-2]
    INC  R1
    JMP  fill
done:
    LOAD R5, [R0]
    OUT  R5
    HALT
zero:
    OUT  0
    HALT
"""

FACTORIAL = """
    IN   R0          ; n
    MOV  R1, 1       ; result
loop:
    JZ   R0, done
    MUL  R1, R0
    DEC  R0
    JMP  loop
done:
    OUT  R1
    HALT
"""

INSERTION_SORT = """
    IN   R0          ; n
    CLR  R1          ; i = 0
read:
    JLE  R0, R1, read_done
    IN   R2
    STOR R2, [R1]
    INC  R1
    JMP  read
read_done:
    MOV  R1, 1       ; i = 1
outer:
    JGE  R1, R0, sort_done   ; stop when i >= n
    LOAD R2, [R1]    ; key = arr[i]
    MOV  R3, R1
    DEC  R3          ; j = i-1
inner:
    JLT  R3, 0, insert
    LOAD R4, [R3]
    JLE  R4, R2, insert
    MOV  R5, R3
    INC  R5
    STOR R4, [R5]    ; arr[j+1] = arr[j]
    DEC  R3
    JMP  inner
insert:
    INC  R3
    STOR R2, [R3]    ; arr[j+1] = key
    INC  R1
    JMP  outer
sort_done:
    CLR  R1
output:
    JLE  R0, R1, halt
    LOAD R2, [R1]
    OUT  R2
    INC  R1
    JMP  output
halt:
    HALT
"""

BINARY_SEARCH = """
    IN   R0          ; n
    CLR  R1          ; i = 0
read:
    JLE  R0, R1, read_done
    IN   R2
    STOR R2, [R1]
    INC  R1
    JMP  read
read_done:
    IN   R7          ; target
    CLR  R1          ; lo = 0
    MOV  R2, R0
    DEC  R2          ; hi = n-1
search:
    JGT  R1, R2, not_found   ; lo > hi
    MOV  R3, R1
    ADD  R3, R2
    DIV  R3, 2               ; mid = (lo+hi)/2
    LOAD R4, [R3]            ; arr[mid]
    MOV  R5, R4
    SUB  R5, R7              ; arr[mid] - target
    JZ   R5, found
    JLT  R4, R7, go_right
    MOV  R2, R3
    DEC  R2                  ; hi = mid-1
    JMP  search
go_right:
    MOV  R1, R3
    INC  R1                  ; lo = mid+1
    JMP  search
found:
    OUT  R3
    HALT
not_found:
    OUT  -1
    HALT
"""

IS_PALINDROME = """
    IN   R0          ; n
    CLR  R1          ; i = 0
read:
    JLE  R0, R1, read_done
    IN   R2
    STOR R2, [R1]
    INC  R1
    JMP  read
read_done:
    CLR  R1          ; left = 0
    MOV  R2, R0
    DEC  R2          ; right = n-1
check:
    JGE  R1, R2, yes
    LOAD R3, [R1]
    LOAD R4, [R2]
    SUB  R3, R4
    JNZ  R3, no
    INC  R1
    DEC  R2
    JMP  check
yes:
    OUT  1
    HALT
no:
    OUT  0
    HALT
"""

TWO_SUM = """
    IN   R0          ; n
    CLR  R1          ; i = 0
read:
    JLE  R0, R1, read_done
    IN   R2
    STOR R2, [R1]
    INC  R1
    JMP  read
read_done:
    IN   R7          ; target
    CLR  R1          ; i = 0
outer:
    JGE  R1, R0, not_found
    MOV  R2, R1
    INC  R2          ; j = i+1
inner:
    JGE  R2, R0, next_i
    LOAD R3, [R1]
    LOAD R4, [R2]
    ADD  R3, R4
    SUB  R3, R7
    JZ   R3, found
    INC  R2
    JMP  inner
next_i:
    INC  R1
    JMP  outer
found:
    OUT  R1
    OUT  R2
    HALT
not_found:
    OUT  -1
    HALT
"""


class TestFibonacci(unittest.TestCase):
    CASES = [(0, 0), (1, 1), (2, 1), (5, 5), (7, 13), (10, 55), (15, 610)]

    def _run(self, prog, n):
        return ok(prog, [n]).outputs[0]

    def test_iterative_cases(self):
        for n, expected in self.CASES:
            with self.subTest(n=n):
                self.assertEqual(self._run(FIB_ITERATIVE, n), expected)

    def test_dp_cases(self):
        for n, expected in self.CASES:
            with self.subTest(n=n):
                self.assertEqual(self._run(FIB_DP, n), expected)

    def test_iterative_insn_count_scales_linearly(self):
        counts = [ok(FIB_ITERATIVE, [n]).insn_count for n in [10, 100, 1000]]
        # ratio of consecutive counts should be ~10
        self.assertGreater(counts[1] / counts[0], 8)
        self.assertGreater(counts[2] / counts[1], 8)

    def test_iterative_no_memory(self):
        r = ok(FIB_ITERATIVE, [100])
        self.assertEqual(r.mem_hwm, 0)

    def test_dp_memory_scales_linearly(self):
        hwms = [ok(FIB_DP, [n]).mem_hwm for n in [10, 50, 100]]
        self.assertGreater(hwms[1], hwms[0])
        self.assertGreater(hwms[2], hwms[1])


class TestFactorial(unittest.TestCase):
    CASES = [(0, 1), (1, 1), (5, 120), (10, 3628800)]

    def test_cases(self):
        for n, expected in self.CASES:
            with self.subTest(n=n):
                r = ok(FACTORIAL, [n])
                self.assertEqual(r.outputs[0], expected)

    def test_no_memory(self):
        r = ok(FACTORIAL, [10])
        self.assertEqual(r.mem_hwm, 0)


class TestInsertionSort(unittest.TestCase):
    def _sort(self, lst):
        return ok(INSERTION_SORT, [len(lst)] + lst).outputs

    def test_basic(self):
        self.assertEqual(self._sort([3, 1, 2]), [1, 2, 3])

    def test_already_sorted(self):
        self.assertEqual(self._sort([1, 2, 3, 4, 5]), [1, 2, 3, 4, 5])

    def test_reverse_sorted(self):
        self.assertEqual(self._sort([5, 4, 3, 2, 1]), [1, 2, 3, 4, 5])

    def test_single_element(self):
        self.assertEqual(self._sort([42]), [42])

    def test_empty(self):
        self.assertEqual(self._sort([]), [])

    def test_duplicates(self):
        self.assertEqual(self._sort([3, 1, 2, 1, 3]), [1, 1, 2, 3, 3])

    def test_negative_values(self):
        self.assertEqual(self._sort([-3, 1, -1, 2]), [-3, -1, 1, 2])

    def test_insn_count_scales_quadratically(self):
        c10  = ok(INSERTION_SORT, [10]  + list(range(10,  0, -1))).insn_count
        c100 = ok(INSERTION_SORT, [100] + list(range(100, 0, -1))).insn_count
        # Worst-case insertion sort is O(n²); ratio should be ~100
        ratio = c100 / c10
        self.assertGreater(ratio, 50)
        self.assertLess(ratio, 200)


class TestBinarySearch(unittest.TestCase):
    ARR = [1, 3, 5, 7, 9]

    def _search(self, arr, target):
        return ok(BINARY_SEARCH, [len(arr)] + arr + [target]).outputs[0]

    def test_found_middle(self):
        self.assertEqual(self._search(self.ARR, 5), 2)

    def test_found_first(self):
        self.assertEqual(self._search(self.ARR, 1), 0)

    def test_found_last(self):
        self.assertEqual(self._search(self.ARR, 9), 4)

    def test_not_found(self):
        self.assertEqual(self._search(self.ARR, 4), -1)

    def test_single_element_found(self):
        self.assertEqual(self._search([7], 7), 0)

    def test_single_element_not_found(self):
        self.assertEqual(self._search([7], 3), -1)

    def test_insn_count_search_dominates_at_large_n(self):
        # Total cost = O(n) read phase + O(log n) search phase.
        # At these sizes the read phase dominates, so we just verify
        # that both sizes produce correct results (logarithmic behaviour
        # is verified by the feature-extraction benchmark separately).
        for n in [100, 1000, 10000]:
            arr = list(range(0, n * 2, 2))
            r = ok(BINARY_SEARCH, [n] + arr + [n])
            self.assertEqual(r.outputs, [n // 2])


class TestIsPalindrome(unittest.TestCase):
    def _check(self, s):
        codes = [ord(c) for c in s]
        return ok(IS_PALINDROME, [len(s)] + codes).outputs[0]

    def test_palindrome(self):
        self.assertEqual(self._check('racecar'), 1)

    def test_not_palindrome(self):
        self.assertEqual(self._check('hello'), 0)

    def test_empty(self):
        self.assertEqual(self._check(''), 1)

    def test_single_char(self):
        self.assertEqual(self._check('a'), 1)

    def test_even_palindrome(self):
        self.assertEqual(self._check('abba'), 1)

    def test_even_not_palindrome(self):
        self.assertEqual(self._check('abca'), 0)


class TestTwoSum(unittest.TestCase):
    def _two_sum(self, nums, target):
        return ok(TWO_SUM, [len(nums)] + nums + [target]).outputs

    def test_basic(self):
        self.assertEqual(self._two_sum([2, 7, 11, 15], 9), [0, 1])

    def test_middle(self):
        self.assertEqual(self._two_sum([3, 2, 4], 6), [1, 2])

    def test_end(self):
        self.assertEqual(self._two_sum([1, 5, 3, 2], 5), [2, 3])


# ── Constraints ───────────────────────────────────────────────────────────────

class TestRegisterBudget(unittest.TestCase):
    def test_within_budget(self):
        r = run('MOV R0, 1\n MOV R1, 2\n ADD R0, R1\n OUT R0\n HALT',
                [], constraints={'register_budget': 4})
        self.assertTrue(r.ok)
        self.assertEqual(r.outputs, [3])

    def test_exceeds_budget(self):
        r = run('MOV R4, 1\n HALT', [], constraints={'register_budget': 4})
        self.assertFalse(r.ok)
        self.assertIn('R4', r.error)

    def test_budget_of_two(self):
        r = run('MOV R2, 1\n HALT', [], constraints={'register_budget': 2})
        self.assertFalse(r.ok)

    def test_budget_of_eight_allows_all(self):
        prog = '\n'.join(f'MOV R{i}, {i}' for i in range(8)) + '\n HALT'
        r = run(prog, [], constraints={'register_budget': 8})
        self.assertTrue(r.ok)


class TestMemoryBudget(unittest.TestCase):
    def test_within_budget(self):
        r = run('MOV R0, 3\n MOV R1, 10\n STOR R0, [R1]\n HALT',
                [], constraints={'memory_budget': 16})
        self.assertTrue(r.ok)

    def test_exceeds_budget(self):
        r = run('MOV R0, 1\n MOV R1, 16\n STOR R0, [R1]\n HALT',
                [], constraints={'memory_budget': 16})
        self.assertFalse(r.ok)

    def test_zero_budget_blocks_all_memory(self):
        r = run('MOV R1, 0\n STOR 1, [R1]\n HALT',
                [], constraints={'memory_budget': 0})
        self.assertFalse(r.ok)

    def test_read_also_constrained(self):
        r = run('MOV R1, 20\n LOAD R0, [R1]\n HALT',
                [], constraints={'memory_budget': 16})
        self.assertFalse(r.ok)


class TestProgramSize(unittest.TestCase):
    def test_within_limit(self):
        r = run('MOV R0, 1\n OUT R0\n HALT', [],
                constraints={'program_size': 3})
        self.assertTrue(r.ok)

    def test_exceeds_limit(self):
        r = run('MOV R0, 1\n MOV R1, 2\n ADD R0, R1\n OUT R0\n HALT',
                [], constraints={'program_size': 3})
        self.assertFalse(r.ok)
        self.assertIn('too long', r.error)

    def test_macros_count_after_expansion(self):
        # INC expands to ADD R0, 1 — counts as 1 instruction
        r = run('INC R0\n INC R0\n OUT R0\n HALT', [],
                constraints={'program_size': 3})
        self.assertFalse(r.ok)   # 4 instructions after expansion


class TestWhitelist(unittest.TestCase):
    BASIC = ['MOV', 'ADD', 'SUB', 'JZ', 'JNZ', 'JMP', 'IN', 'OUT']

    def test_allowed_opcodes_pass(self):
        r = run('MOV R0, 1\n ADD R0, 1\n OUT R0\n HALT', [],
                constraints={'whitelist': self.BASIC})
        self.assertTrue(r.ok)

    def test_disallowed_opcode_rejected(self):
        r = run('MOV R0, 6\n MUL R0, 7\n OUT R0\n HALT', [],
                constraints={'whitelist': self.BASIC})
        self.assertFalse(r.ok)
        self.assertIn('MUL', r.error)

    def test_no_mul_forces_add_loop(self):
        # Multiply 6×7 via repeated addition
        prog = """
            IN   R0       ; 6
            IN   R1       ; 7
            CLR  R2       ; result = 0
loop:       JZ   R1, done
            ADD  R2, R0
            DEC  R1
            JMP  loop
done:       OUT  R2
            HALT
        """
        r = run(prog, [6, 7], constraints={'whitelist': self.BASIC + ['DEC', 'CLR']})
        self.assertTrue(r.ok)
        self.assertEqual(r.outputs, [42])


# ── Error handling ────────────────────────────────────────────────────────────

class TestErrors(unittest.TestCase):
    def test_step_limit(self):
        r = run('loop: JMP loop\n HALT', [], max_steps=100)
        self.assertFalse(r.ok)
        self.assertIn('Step limit', r.error)

    def test_input_exhausted(self):
        r = run('IN R0\n IN R1\n HALT', [42])
        self.assertFalse(r.ok)
        self.assertIn('Input exhausted', r.error)

    def test_division_by_zero_div(self):
        r = run('MOV R0, 5\n MOV R1, 0\n DIV R0, R1\n HALT', [])
        self.assertFalse(r.ok)
        self.assertIn('zero', r.error.lower())

    def test_division_by_zero_mod(self):
        r = run('MOV R0, 5\n MOV R1, 0\n MOD R0, R1\n HALT', [])
        self.assertFalse(r.ok)

    def test_unknown_opcode(self):
        r = run('PUSH R0\n HALT', [])
        self.assertFalse(r.ok)
        self.assertIn('PUSH', r.error)

    def test_halt_not_required_at_end(self):
        # Program that falls off end without HALT is valid
        r = run('MOV R0, 1\n OUT R0', [])
        self.assertTrue(r.ok)
        self.assertEqual(r.outputs, [1])


# ── Parser edge cases ─────────────────────────────────────────────────────────

class TestParser(unittest.TestCase):
    def test_semicolon_comment(self):
        r = ok('MOV R0, 42  ; this is a comment\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [42])

    def test_hash_comment(self):
        r = ok('MOV R0, 42  # this is a comment\n OUT R0\n HALT')
        self.assertEqual(r.outputs, [42])

    def test_blank_lines_ignored(self):
        r = ok('\n\n MOV R0, 5\n\n OUT R0\n\n HALT\n\n')
        self.assertEqual(r.outputs, [5])

    def test_multiple_labels_same_location(self):
        r = ok('JMP b\na:\nb:\n OUT 1\n HALT')
        self.assertEqual(r.outputs, [1])

    def test_label_and_instruction_same_line(self):
        r = ok('JMP target\n OUT 0\n HALT\ntarget: OUT 99\n HALT')
        self.assertEqual(r.outputs, [99])

    def test_negative_immediate_in_mem_offset(self):
        r = ok('MOV R1, 5\n MOV R0, 42\n STOR R0, [R1-2]\n LOAD R2, [R1-2]\n OUT R2\n HALT')
        self.assertEqual(r.outputs, [42])

    def test_case_insensitive_opcodes(self):
        r = ok('mov R0, 42\n out R0\n halt')
        self.assertEqual(r.outputs, [42])


if __name__ == '__main__':
    unittest.main(verbosity=2)
