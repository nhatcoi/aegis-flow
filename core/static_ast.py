"""AST / control-flow metrics for generated functions (Chương 1.4 CFG, Chương 3).

Python functions are analysed with the ``ast`` module; C functions with a
lightweight token scan of the comment-stripped source. The metrics feed the
report table (variables, branch conditions, loops, McCabe V(G), nesting depth)
and the branch conditions are reused by the concolic fuzzer.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from .c_analyzer import _functions, _strip_comments
from .codegen import GeneratedFunction


@dataclass
class FunctionMetrics:
    name: str
    language: str
    variables: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    loops: list[str] = field(default_factory=list)
    cyclomatic: int = 1  # McCabe V(G) = number of decisions + 1
    nesting_depth: int = 0
    lines_of_code: int = 0


def _python_metrics(name: str, code: str) -> FunctionMetrics:
    tree = ast.parse(code)
    func = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name), None)
    m = FunctionMetrics(name, "python")
    if func is None:
        return m
    variables = [a.arg for a in func.args.args]
    decisions = 0

    def visit(node: ast.AST, depth: int) -> None:
        nonlocal decisions
        for child in ast.iter_child_nodes(node):
            d = depth
            if isinstance(child, (ast.If, ast.While, ast.For, ast.IfExp)):
                decisions += 1
                d = depth + 1
                m.nesting_depth = max(m.nesting_depth, d)
                if isinstance(child, (ast.If, ast.While, ast.IfExp)):
                    m.conditions.append(ast.unparse(child.test))
                if isinstance(child, (ast.While, ast.For)):
                    m.loops.append(ast.unparse(child).splitlines()[0])
            elif isinstance(child, ast.BoolOp):
                decisions += len(child.values) - 1
            elif isinstance(child, ast.ExceptHandler):
                decisions += 1
            elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store) and child.id not in variables:
                variables.append(child.id)
            visit(child, d)

    visit(func, 0)
    m.variables = variables
    m.cyclomatic = decisions + 1
    m.lines_of_code = len([ln for ln in ast.unparse(func).splitlines() if ln.strip()])
    return m


C_DECISION_RE = re.compile(r"\b(if|while|for|case)\b|&&|\|\||\?")
C_DECL_RE = re.compile(r"\b(?:int|char|size_t|long|short|unsigned|float|double)\b[\s\*]*([A-Za-z_]\w*)\s*(?:\[|=|;|,|\))")


def _c_metrics(name: str, code: str) -> FunctionMetrics:
    clean = _strip_comments(code)
    m = FunctionMetrics(name, "c")
    for fname, _, body in _functions(clean):
        if fname != name:
            continue
        text = "\n".join(body)
        m.variables = list(dict.fromkeys(v for v in C_DECL_RE.findall(text) if v != name))
        m.conditions = [c.strip() for c in re.findall(r"\bif\s*\((.*)\)\s*(?:\{|return|$)", text, re.MULTILINE)]
        m.loops = [ln.strip() for ln in body if re.search(r"\b(for|while)\s*\(", ln)]
        m.cyclomatic = len(C_DECISION_RE.findall(text)) + 1
        depth = deepest = 0
        for ch in text:
            if ch == "{":
                depth += 1
                deepest = max(deepest, depth)
            elif ch == "}":
                depth -= 1
        m.nesting_depth = max(deepest, 1)
        m.lines_of_code = len([ln for ln in body if ln.strip()])
    return m


def function_metrics(gf: GeneratedFunction, version: str = "v0") -> FunctionMetrics:
    code = gf.code_vulnerable if version == "v0" else gf.code_safe
    if gf.language == "python":
        return _python_metrics(gf.spec.name, code)
    return _c_metrics(gf.spec.name, code)
