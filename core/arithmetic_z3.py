"""Arithmetic and SMT integer overflow checker using Z3 Theorem Prover."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

import z3

from .spec_loader import ArithmeticCheck


@dataclass
class SMTCheckResult:
    name: str
    condition_sat: bool
    overflow_possible: bool
    model_values: dict[str, int] = field(default_factory=dict)
    overflow_values: dict[str, int] = field(default_factory=dict)
    overflow_evaluated: int | None = None
    details: str = ""
    status: str = ""  # "overflow" | "safe" | "error"
    bv_overflow: bool = False
    bv_values: dict[str, int | None] = field(default_factory=dict)
    wrapped_value: int | None = None
    patch_guard: str | None = None
    patch_status: str = "n/a"  # "unsat" (patch proven) | "sat" | "n/a"
    overflow_under_condition: bool = False


INT32_MIN = -2147483648
INT32_MAX = 2147483647


def _ast_to_z3(node: ast.AST, env: dict[str, z3.ArithRef]) -> Any:
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        raise ValueError(f"Biến không xác định trong biểu thức SMT: {node.id}")

    elif isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return z3.BoolVal(node.value)
        if isinstance(node.value, int):
            sample = next(iter(env.values()), None)
            if isinstance(sample, z3.BitVecRef):
                return z3.BitVecVal(node.value, sample.size())
            return z3.IntVal(node.value)
        raise ValueError(f"Hằng số không được hỗ trợ: {node.value}")

    elif isinstance(node, ast.UnaryOp):
        operand = _ast_to_z3(node.operand, env)
        if isinstance(node.op, ast.USub):
            return -operand
        elif isinstance(node.op, ast.Not):
            return z3.Not(operand)

    elif isinstance(node, ast.BinOp):
        left = _ast_to_z3(node.left, env)
        right = _ast_to_z3(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        elif isinstance(node.op, ast.FloorDiv):
            return left / right
        elif isinstance(node.op, ast.Mod):
            return left % right

    elif isinstance(node, ast.Compare):
        left = _ast_to_z3(node.left, env)
        comps = []
        curr = left
        for op, comparator in zip(node.ops, node.comparators):
            right = _ast_to_z3(comparator, env)
            if isinstance(op, ast.Eq):
                comps.append(curr == right)
            elif isinstance(op, ast.NotEq):
                comps.append(curr != right)
            elif isinstance(op, ast.Lt):
                comps.append(curr < right)
            elif isinstance(op, ast.LtE):
                comps.append(curr <= right)
            elif isinstance(op, ast.Gt):
                comps.append(curr > right)
            elif isinstance(op, ast.GtE):
                comps.append(curr >= right)
            curr = right
        return z3.And(*comps) if len(comps) > 1 else comps[0]

    elif isinstance(node, ast.BoolOp):
        values = [_ast_to_z3(val, env) for val in node.values]
        if isinstance(node.op, ast.And):
            return z3.And(*values)
        elif isinstance(node.op, ast.Or):
            return z3.Or(*values)

    raise ValueError(f"Toán tử AST chưa được hỗ trợ: {type(node)}")


def parse_to_z3(expr_str: str, env: dict[str, z3.ArithRef]) -> Any:
    tree = ast.parse(expr_str.strip(), mode="eval")
    return _ast_to_z3(tree.body, env)


def _int(v: Any) -> int | None:
    try:
        return int(str(v))
    except ValueError:
        return None


def _bv_int(v: Any) -> int | None:
    return v.as_signed_long() if isinstance(v, z3.BitVecNumRef) else None


def _int32_bounds(env: dict[str, z3.ArithRef]) -> list[Any]:
    return [z3.And(x >= INT32_MIN, x <= INT32_MAX) for x in env.values()]


def patch_guard(expr: str) -> str | None:
    """C guard that v1 uses to reject overflowing `a + b` / `a - b` (see core.codegen)."""
    m = re.fullmatch(r"\s*([A-Za-z_]\w*)\s*([+-])\s*([A-Za-z_]\w*)\s*", expr or "")
    if not m:
        return None
    a, op, b = m.groups()
    if op == "+":
        return f"({b} > 0 and {a} > INT_MAX - {b}) or ({b} < 0 and {a} < INT_MIN - {b})"
    return f"({b} < 0 and {a} > INT_MAX + {b}) or ({b} > 0 and {a} < INT_MIN + {b})"


def check_arithmetic_spec(check: ArithmeticCheck) -> SMTCheckResult:
    env = {v: z3.Int(v) for v in check.int_vars}
    bounds = _int32_bounds(env)
    result = SMTCheckResult(name=check.name, condition_sat=True, overflow_possible=False)

    try:
        cond = parse_to_z3(check.condition, env) if check.condition else None
        expr = parse_to_z3(check.overflow_expr, env) if check.overflow_expr else None
    except Exception as e:  # noqa: BLE001 - surface any parse problem to the user
        result.condition_sat = False
        result.details = f"Lỗi phân tích cú pháp biểu thức: {e}"
        result.status = "error"
        return result

    # 1. Business condition (with every variable restricted to int32)
    if cond is not None:
        solver = z3.Solver()
        solver.add(*bounds, cond)
        result.condition_sat = solver.check() == z3.sat
        if result.condition_sat:
            m = solver.model()
            result.model_values = {v: _int(m.eval(env[v], model_completion=True)) for v in check.int_vars}

    # 2. Mathematical overflow: exact value outside int32 while inputs are int32
    if expr is not None:
        overflow = z3.Or(expr > INT32_MAX, expr < INT32_MIN)
        solver = z3.Solver()
        solver.add(*bounds, overflow)
        if cond is not None and result.condition_sat:
            solver.push()
            solver.add(cond)  # prefer a witness that also satisfies the business condition
            if solver.check() == z3.sat:
                result.overflow_under_condition = True
            else:
                solver.pop()
        if solver.check() == z3.sat:
            m = solver.model()
            result.overflow_possible = True
            result.overflow_values = {v: _int(m.eval(env[v], model_completion=True)) for v in check.int_vars}
            result.overflow_evaluated = _int(m.eval(expr))

        # 3. Bit-vector semantics: what a 32-bit C int actually computes (wrap-around)
        bv = {v: z3.BitVec(v, 32) for v in check.int_vars}
        wide = {v: z3.SignExt(32, x) for v, x in bv.items()}
        try:
            r32 = parse_to_z3(check.overflow_expr, bv)
            r64 = parse_to_z3(check.overflow_expr, wide)
            solver = z3.Solver()
            solver.add(z3.SignExt(32, r32) != r64)
            if check.condition and result.overflow_under_condition:
                solver.push()
                solver.add(parse_to_z3(check.condition, bv))
                if solver.check() != z3.sat:
                    solver.pop()  # the condition itself may be written on the wrapped value; drop it
            if solver.check() == z3.sat:
                m = solver.model()
                result.bv_overflow = True
                result.bv_values = {v: _bv_int(m.eval(x, model_completion=True)) for v, x in bv.items()}
                result.wrapped_value = _bv_int(m.eval(r32))
        except Exception:  # noqa: BLE001, S110 - bit-vector view is best effort (e.g. unsupported ops)
            pass

        # 4. Re-verify with the v1 guard as precondition: overflow must be UNSAT
        guard = patch_guard(check.overflow_expr or "")
        if guard:
            genv = dict(env, INT_MAX=z3.IntVal(INT32_MAX), INT_MIN=z3.IntVal(INT32_MIN))
            solver = z3.Solver()
            solver.add(*bounds, z3.Not(parse_to_z3(guard, genv)), z3.Or(expr > INT32_MAX, expr < INT32_MIN))
            result.patch_guard = guard
            result.patch_status = str(solver.check())

    result.status = "overflow" if result.overflow_possible else "safe"
    result.details = _format(check, result)
    return result


def _format(check: ArithmeticCheck, r: SMTCheckResult) -> str:
    lines = [f"=== KIỂM TRA SMT / SỐ HỌC (Z3): {check.name} ===",
             f"- Miền biến: mọi biến {', '.join(check.int_vars)} ∈ [{INT32_MIN}, {INT32_MAX}] (int32)"]
    if check.condition:
        lines.append(f"- Điều kiện nghiệp vụ: `{check.condition}`")
        lines.append(f"  -> {'SAT' if r.condition_sat else 'UNSAT'}"
                     + (f", ví dụ: {r.model_values}" if r.condition_sat else ""))
    if check.overflow_expr:
        lines.append(f"- Biểu thức: `{check.overflow_expr}`")
        if r.overflow_possible:
            where = " (thỏa cả điều kiện nghiệp vụ)" if r.overflow_under_condition else ""
            lines.append(f"  -> SAT [CWE-190]: có thể TRÀN int32{where}. Model: {r.overflow_values}, "
                         f"giá trị đúng = {r.overflow_evaluated}")
        else:
            lines.append("  -> UNSAT: không tồn tại input int32 nào làm biểu thức tràn.")
        if r.bv_overflow:
            lines.append(f"  -> Bit-vector 32-bit (C thật): {r.bv_values} cho kết quả wrap-around = {r.wrapped_value}")
        if r.patch_guard:
            verdict = "UNSAT — bản vá loại bỏ hoàn toàn tràn số" if r.patch_status == "unsat" \
                else f"{r.patch_status.upper()} — bản vá CHƯA đủ"
            lines.append(f"- Sau vá (v1 từ chối khi `{r.patch_guard}`): {verdict}")
    return "\n".join(lines)


def check_all_arithmetic(checks: list[ArithmeticCheck]) -> list[SMTCheckResult]:
    return [check_arithmetic_spec(ac) for ac in checks]
