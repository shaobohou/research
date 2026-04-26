"""
ISA interpreter for MAP-Elites coding benchmark.

Two ISA tiers:
  core     — 12 opcodes only; programs fall off end to terminate
  extended — adds MOD, JNZ, JLE, HALT + 6 macros (default)

Machine state:
  - Registers R0-R7 (32-bit signed, init 0)
  - Memory: sparse flat array of 32-bit signed ints, addr 0-65535
  - Input tape, output tape
  - insn_count: incremented on every executed instruction
  - mem_hwm: high-water mark of memory addresses written
"""

import math
import re
from dataclasses import dataclass
from typing import Optional

# ── ISA tiers ─────────────────────────────────────────────────────────────────

CORE_OPCODES = frozenset({
    'MOV', 'ADD', 'SUB', 'MUL', 'DIV',
    'LOAD', 'STOR',
    'JMP', 'JZ', 'JLT',
    'IN', 'OUT',
})

EXTENDED_OPCODES = frozenset({'MOD', 'JNZ', 'JLE', 'HALT'})

MACRO_NAMES = frozenset({'INC', 'DEC', 'CLR', 'NEG', 'JGT', 'JGE'})

ALL_OPCODES = CORE_OPCODES | EXTENDED_OPCODES

# ── Constants ─────────────────────────────────────────────────────────────────

REGISTERS  = {f'R{i}': i for i in range(8)}
_MAX_ADDR  = 65535
_MAX32     = 2**31 - 1
_MIN32     = -(2**31)

def _wrap32(v: int) -> int:
    return ((v + 2**31) % 2**32) - 2**31

def _tdiv(a: int, b: int) -> int:
    """Integer division truncated toward zero (C-style)."""
    return math.trunc(a / b)


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    outputs:    list
    insn_count: int
    mem_hwm:    int
    error:      Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


# ── Parser ────────────────────────────────────────────────────────────────────

# Macros: name -> callable(args) -> list of (opcode, args) tuples
_MACROS = {
    'JGT': lambda a: [('JLT', [a[1], a[0], a[2]])],
    'JGE': lambda a: [('JLE', [a[1], a[0], a[2]])],
    'INC': lambda a: [('ADD', [a[0], '1'])],
    'DEC': lambda a: [('SUB', [a[0], '1'])],
    'CLR': lambda a: [('MOV', [a[0], '0'])],
    'NEG': lambda a: [('MUL', [a[0], '-1'])],
}

_MEM_RE  = re.compile(r'^\[(\w+)([+-]\d+)?\]$')
_LABEL_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def _split_args(s: str) -> list[str]:
    """Split comma-separated args respecting brackets."""
    args, cur, depth = [], [], 0
    for ch in s:
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
        if ch == ',' and depth == 0:
            args.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        args.append(''.join(cur).strip())
    return [a for a in args if a]


def parse(source: str) -> tuple[list, dict]:
    """
    Parse assembly source.
    Returns (instructions, label_map) where:
      instructions: list of (opcode, args_list)
      label_map:    dict label -> instruction index
    """
    instructions = []
    label_map    = {}
    pending      = []          # labels waiting to bind to next instruction

    for raw in source.splitlines():
        line = raw.split(';')[0].split('#')[0].strip()
        if not line:
            continue

        # Peel off any "label:" prefixes (there may be multiple)
        while True:
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:(.*)', line)
            if not m:
                break
            pending.append(m.group(1))
            line = m.group(2).strip()

        if not line:
            continue   # label-only line; labels will bind to next instruction

        parts  = line.split(None, 1)
        opcode = parts[0].upper()
        args   = _split_args(parts[1]) if len(parts) > 1 else []

        expanded = _MACROS[opcode](args) if opcode in _MACROS else [(opcode, args)]

        for i, (op, op_args) in enumerate(expanded):
            idx = len(instructions)
            if i == 0:
                for lbl in pending:
                    label_map[lbl] = idx
                pending = []
            instructions.append((op, op_args))

    # Labels at end of file point past last instruction
    for lbl in pending:
        label_map[lbl] = len(instructions)

    return instructions, label_map


# ── Executor ──────────────────────────────────────────────────────────────────

def run(source: str,
        inputs:      list[int],
        constraints: dict | None = None,
        max_steps:   int         = 10_000_000,
        isa:         str         = 'extended') -> RunResult:
    """
    Execute an ISA program.

    isa: 'core'     — only CORE_OPCODES allowed; macros and HALT forbidden
         'extended' — CORE_OPCODES + EXTENDED_OPCODES + macros (default)

    constraints keys (all optional):
      register_budget  int   max register index + 1 (e.g. 4 → R0-R3 only)
      memory_budget    int   max writable/readable address (exclusive)
      program_size     int   max instruction count after macro expansion
      whitelist        list  allowed opcodes (strings); overrides isa tier
    """
    constraints = constraints or {}

    # ── ISA tier check (scans raw source before macro expansion) ─────────────
    if isa == 'core':
        disallowed = EXTENDED_OPCODES | MACRO_NAMES
        for raw in source.splitlines():
            line = raw.split(';')[0].split('#')[0].strip()
            while re.match(r'^[A-Za-z_][A-Za-z0-9_]*\s*:', line):
                line = line.split(':', 1)[1].strip()
            if not line:
                continue
            token = line.split()[0].upper()
            if token in disallowed:
                return RunResult([], 0, 0,
                    f'{token!r} is not in the core ISA')

    try:
        instructions, label_map = parse(source)
    except Exception as e:
        return RunResult([], 0, 0, f'Parse error: {e}')

    # ── Static constraint checks ──────────────────────────────────────────────

    prog_size = len(instructions)
    if 'program_size' in constraints and prog_size > constraints['program_size']:
        return RunResult([], 0, 0,
            f'Program too long: {prog_size} > {constraints["program_size"]}')

    if 'whitelist' in constraints:
        allowed = {o.upper() for o in constraints['whitelist']} | {'HALT'}
        for op, _ in instructions:
            if op not in allowed:
                return RunResult([], 0, 0, f'Opcode {op!r} not in whitelist')

    reg_budget = constraints.get('register_budget', 8)
    mem_budget = constraints.get('memory_budget')   # None = unlimited

    if reg_budget < 8:
        for op, args in instructions:
            for a in args:
                if a in REGISTERS and REGISTERS[a] >= reg_budget:
                    return RunResult([], 0, 0,
                        f'Register {a} exceeds budget (R0-R{reg_budget-1})')

    # ── Machine state ─────────────────────────────────────────────────────────

    regs       = [0] * 8
    mem        = {}            # sparse: addr -> value
    pc         = 0
    insn_count = 0
    mem_hwm    = 0
    outputs    = []
    inp        = iter(inputs)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get(token: str) -> int:
        """Resolve register name or integer literal to value."""
        if token in REGISTERS:
            return regs[REGISTERS[token]]
        return int(token)

    def _set(token: str, value: int):
        if token not in REGISTERS:
            raise ValueError(f'Not a register: {token!r}')
        regs[REGISTERS[token]] = _wrap32(value)

    def _addr(token: str) -> int:
        """Parse [base+off] or [base] to an integer address."""
        m = _MEM_RE.match(token)
        if not m:
            raise ValueError(f'Invalid memory operand: {token!r}')
        base = _get(m.group(1))
        off  = int(m.group(2)) if m.group(2) else 0
        return base + off

    def _mem_read(addr: int) -> int:
        if not (0 <= addr <= _MAX_ADDR):
            raise ValueError(f'Address {addr} out of range')
        if mem_budget is not None and addr >= mem_budget:
            raise ValueError(f'Address {addr} exceeds memory budget {mem_budget}')
        return mem.get(addr, 0)

    def _mem_write(addr: int, value: int):
        nonlocal mem_hwm
        if not (0 <= addr <= _MAX_ADDR):
            raise ValueError(f'Address {addr} out of range')
        if mem_budget is not None and addr >= mem_budget:
            raise ValueError(f'Address {addr} exceeds memory budget {mem_budget}')
        mem[addr] = _wrap32(value)
        if addr > mem_hwm:
            mem_hwm = addr

    def _jump(label: str):
        nonlocal pc
        if label not in label_map:
            raise ValueError(f'Unknown label: {label!r}')
        pc = label_map[label]

    # ── Execution loop ────────────────────────────────────────────────────────

    while pc < len(instructions):
        if insn_count >= max_steps:
            return RunResult(outputs, insn_count, mem_hwm, 'Step limit exceeded')

        op, args = instructions[pc]
        insn_count += 1
        pc += 1

        try:
            if op == 'MOV':
                _set(args[0], _get(args[1]))
            elif op == 'ADD':
                _set(args[0], _get(args[0]) + _get(args[1]))
            elif op == 'SUB':
                _set(args[0], _get(args[0]) - _get(args[1]))
            elif op == 'MUL':
                _set(args[0], _get(args[0]) * _get(args[1]))
            elif op == 'DIV':
                b = _get(args[1])
                if b == 0:
                    return RunResult(outputs, insn_count, mem_hwm, 'Division by zero')
                _set(args[0], _tdiv(_get(args[0]), b))
            elif op == 'MOD':
                b = _get(args[1])
                if b == 0:
                    return RunResult(outputs, insn_count, mem_hwm, 'Division by zero')
                _set(args[0], _get(args[0]) % b)
            elif op == 'LOAD':
                _set(args[0], _mem_read(_addr(args[1])))
            elif op == 'STOR':
                _mem_write(_addr(args[1]), _get(args[0]))
            elif op == 'JMP':
                _jump(args[0])
            elif op == 'JZ':
                if _get(args[0]) == 0:
                    _jump(args[1])
            elif op == 'JNZ':
                if _get(args[0]) != 0:
                    _jump(args[1])
            elif op == 'JLT':
                if _get(args[0]) < _get(args[1]):
                    _jump(args[2])
            elif op == 'JLE':
                if _get(args[0]) <= _get(args[1]):
                    _jump(args[2])
            elif op == 'IN':
                try:
                    _set(args[0], next(inp))
                except StopIteration:
                    return RunResult(outputs, insn_count, mem_hwm, 'Input exhausted')
            elif op == 'OUT':
                outputs.append(_get(args[0]))
            elif op == 'HALT':
                break
            else:
                return RunResult(outputs, insn_count, mem_hwm, f'Unknown opcode: {op!r}')

        except ValueError as e:
            return RunResult(outputs, insn_count, mem_hwm, str(e))

    return RunResult(outputs, insn_count, mem_hwm)
