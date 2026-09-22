import hashlib
import json
import math
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .engine import in_domain


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Variable(StrictModel):
    label: str = Field(min_length=1, max_length=120)
    values: list[Any] = Field(min_length=1, max_length=12)
    initial: Any

    @model_validator(mode="after")
    def validate_domain(self):
        kind = type(self.values[0])
        if kind not in (bool, int, str) or any(type(v) is not kind for v in self.values):
            raise ValueError("Miền phải đồng nhất: boolean, integer hoặc string")
        if len(set(self.values)) != len(self.values):
            raise ValueError("Miền có giá trị trùng")
        if any(isinstance(v, str) and (not v or len(v) > 60 or v.startswith("$")) for v in self.values):
            raise ValueError("Giá trị chuỗi không hợp lệ")
        if kind is int and any(abs(v) > 1_000_000_000 for v in self.values):
            raise ValueError("Giá trị integer quá lớn")
        if not in_domain(self.initial, self.values):
            raise ValueError("Giá trị khởi đầu ngoài miền")
        return self


class Transition(StrictModel):
    event: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=120)
    from_states: list[str] = Field(min_length=1, max_length=12)
    to_state: str
    guard: Any = True
    effects: dict[str, Any] = Field(default_factory=dict)


class Property(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=160)
    expression: Any


def expression_type(expr, variables, inputs, depth=0):
    if depth > 12:
        raise ValueError("Biểu thức lồng quá 12 cấp")
    if isinstance(expr, str) and expr.startswith("$"):
        name = expr[1:]
        definitions = inputs if name.startswith("input.") else variables
        key = name.removeprefix("input.")
        if key not in definitions:
            raise ValueError(f"Biến không tồn tại: {expr}")
        return type(definitions[key].values[0])
    if type(expr) in (bool, int, str):
        if isinstance(expr, str) and len(expr) > 120:
            raise ValueError("Hằng chuỗi quá dài")
        return type(expr)
    if not isinstance(expr, dict) or len(expr) != 1:
        raise ValueError("Biểu thức phải là hằng, $biến hoặc một toán tử JSON")
    op, args = next(iter(expr.items()))
    arity = {"eq": 2, "ne": 2, "lt": 2, "le": 2, "add": 2, "sub": 2, "not": 1, "implies": 2}
    if not isinstance(args, list) or not 1 <= len(args) <= 20:
        raise ValueError("Danh sách đối số không hợp lệ")
    if op not in {"and", "or"} and (op not in arity or len(args) != arity[op]):
        raise ValueError(f"Toán tử hoặc số đối số không hợp lệ: {op}")
    types = [expression_type(arg, variables, inputs, depth + 1) for arg in args]
    expected = bool if op in {"and", "or", "not", "implies"} else int
    if op in {"eq", "ne"}:
        if types[0] is not types[1]:
            raise ValueError("Không so sánh hai kiểu khác nhau")
    elif any(kind is not expected for kind in types):
        raise ValueError(f"Sai kiểu đối số cho {op}")
    return int if op in {"add", "sub"} else bool


class Specification(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=2000)
    assumptions: list[str] = Field(max_length=12)
    variables: dict[str, Variable] = Field(min_length=1, max_length=12)
    inputs: dict[str, Variable] = Field(max_length=7)
    transitions: list[Transition] = Field(min_length=1, max_length=24)
    properties: list[Property] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_semantics(self):
        for name in [*self.variables, *self.inputs]:
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", name):
                raise ValueError(f"Tên biến không hợp lệ: {name}")
        if "status" not in self.variables or type(self.variables["status"].values[0]) is not str:
            raise ValueError("Cần biến status với miền chuỗi")
        if math.prod(len(v.values) for v in self.variables.values()) > 4096:
            raise ValueError("Bản thử nghiệm giới hạn 4096 tổ hợp trạng thái")
        if math.prod(len(v.values) for v in self.inputs.values()) > 128:
            raise ValueError("Bản thử nghiệm giới hạn 128 tổ hợp đầu vào")
        if len({t.event for t in self.transitions}) != len(self.transitions):
            raise ValueError("Mỗi event chỉ có một định nghĩa chuyển trạng thái")
        if len({p.id for p in self.properties}) != len(self.properties):
            raise ValueError("ID thuộc tính bị trùng")
        statuses = self.variables["status"].values
        for transition in self.transitions:
            if transition.event == "stutter":
                raise ValueError("stutter là sự kiện dành riêng cho bộ kiểm chứng")
            if any(s not in statuses for s in [*transition.from_states, transition.to_state]):
                raise ValueError(f"Trạng thái không tồn tại trong {transition.event}")
            if expression_type(transition.guard, self.variables, self.inputs) is not bool:
                raise ValueError("Guard phải có kiểu boolean")
            for name, expr in transition.effects.items():
                if name not in self.variables or name == "status":
                    raise ValueError(f"Biến effect không hợp lệ: {name}; dùng to_state cho status")
                if expression_type(expr, self.variables, self.inputs) is not type(self.variables[name].initial):
                    raise ValueError(f"Sai kiểu effect: {name}")
        for prop in self.properties:
            if expression_type(prop.expression, self.variables, {}) is not bool:
                raise ValueError("Thuộc tính trạng thái phải có kiểu boolean, không dùng input")
        return self


def spec_hash(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
