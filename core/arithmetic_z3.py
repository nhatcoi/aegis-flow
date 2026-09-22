"""Arithmetic and SMT integer overflow checker using Z3 Theorem Prover."""
from __future__ import annotations

import ast
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


INT32_MIN = -2147483648
INT32_MAX = 2147483647


def _ast_to_z3(node: ast.AST, env: dict[str, z3.ArithRef]) -> Any:
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        raise ValueError(f"Biến không xác định trong biểu thức SMT: {node.id}")

    elif isinstance(node, ast.Constant):
        if isinstance(node.value, int):
            return z3.IntVal(node.value)
        elif isinstance(node.value, bool):
            return z3.BoolVal(node.value)
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


def check_arithmetic_spec(check: ArithmeticCheck) -> SMTCheckResult:
    # Build Z3 environment
    env = {v: z3.Int(v) for v in check.int_vars}

    # 1. Check condition satisfiability
    cond_sat = False
    model_vals: dict[str, int] = {}

    solver = z3.Solver()
    if check.condition:
        try:
            z3_cond = parse_to_z3(check.condition, env)
            solver.add(z3_cond)
            if solver.check() == z3.sat:
                cond_sat = True
                m = solver.model()
                for v in check.int_vars:
                    val = m.eval(env[v])
                    if val is not None:
                        try:
                            model_vals[v] = int(str(val))
                        except ValueError:
                            pass
        except Exception as e:
            return SMTCheckResult(
                name=check.name,
                condition_sat=False,
                overflow_possible=False,
                details=f"Lỗi phân tích cú pháp biểu thức điều kiện: {e}",
            )
    else:
        cond_sat = True

    # 2. Check 32-bit Integer Overflow
    overflow_possible = False
    overflow_vals: dict[str, int] = {}
    overflow_evaluated = None

    if check.overflow_expr:
        try:
            ovf_solver = z3.Solver()
            if check.condition:
                z3_cond = parse_to_z3(check.condition, env)
                ovf_solver.add(z3_cond)

            z3_expr = parse_to_z3(check.overflow_expr, env)
            # Overflow occurs if expr > INT32_MAX or expr < INT32_MIN
            ovf_condition = z3.Or(z3_expr > INT32_MAX, z3_expr < INT32_MIN)
            ovf_solver.add(ovf_condition)

            if ovf_solver.check() == z3.sat:
                overflow_possible = True
                m = ovf_solver.model()
                for v in check.int_vars:
                    val = m.eval(env[v])
                    if val is not None:
                        try:
                            overflow_vals[v] = int(str(val))
                        except ValueError:
                            pass
                eval_val = m.eval(z3_expr)
                if eval_val is not None:
                    try:
                        overflow_evaluated = int(str(eval_val))
                    except ValueError:
                        pass
        except Exception as e:
            return SMTCheckResult(
                name=check.name,
                condition_sat=cond_sat,
                overflow_possible=False,
                model_values=model_vals,
                details=f"Lỗi kiểm tra tràn số: {e}",
            )

    # Format explanation details
    lines = [f"=== KIỂM TRA SMT / SỐ HỌC (Z3 Solver): {check.name} ==="]
    if check.condition:
        lines.append(f"- Điều kiện: `{check.condition}`")
        if cond_sat:
            lines.append(f"  -> Thỏa được (SAT). Ví dụ bộ giá trị thỏa mãn: {model_vals}")
        else:
            lines.append("  -> Không thỏa được (UNSAT).")

    if check.overflow_expr:
        lines.append(f"- Biểu thức kiểm tra tràn số: `{check.overflow_expr}` (Miền int32: [{INT32_MIN}, {INT32_MAX}])")
        if overflow_possible:
            lines.append(
                f"  -> CẢNH BÁO [CWE-190]: Phát hiện khả năng TRÀN SỐ NGUYÊN 32-BIT!\n"
                f"     Bộ giá trị gây tràn: {overflow_vals}\n"
                f"     Giá trị biểu thức tính được: {overflow_evaluated} (vượt quá INT_MAX {INT32_MAX})"
            )
        else:
            lines.append("  -> An toàn: Không tìm thấy giá trị nào gây tràn số int32 trong điều kiện đã cho.")

    return SMTCheckResult(
        name=check.name,
        condition_sat=cond_sat,
        overflow_possible=overflow_possible,
        model_values=model_vals,
        overflow_values=overflow_vals,
        overflow_evaluated=overflow_evaluated,
        details="\n".join(lines),
    )


def check_all_arithmetic(checks: list[ArithmeticCheck]) -> list[SMTCheckResult]:
    return [check_arithmetic_spec(ac) for ac in checks]
