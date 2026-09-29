"""Evidence-based CWE classification (Chương 1.2 CWE/CVE, tổng hợp Chương 1–4).

A finding is only "confirmed" when an analysis actually produced it (static
scanner, sanitizer, SMT model, fuzzer crash, CTL/BMC counterexample). Bugs
that are declared in the spec but that no tool reproduced are kept as
"declared-only" so the report states that gap honestly. For each finding the
v1 (patched) evidence is collected as well, producing the before/after table.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .arithmetic_z3 import SMTCheckResult
from .bmc import BMCResult
from .c_analyzer import Finding, analyze_c_source
from .codegen import GeneratedFunction, generate_all_functions
from .fuzzing import FuzzResult, fuzz_generated
from .kripke import KripkeCheckReport
from .spec_loader import Specification
from .toolchain import SanitizerRun


@dataclass
class CWEFinding:
    cwe_id: str
    cwe_name: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    source_component: str
    description: str
    illustrative_cve: str
    remediation: str
    status: str = "confirmed"  # "confirmed" | "declared-only"
    chapter: str = ""
    tools: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)  # v0 evidence lines
    after: list[str] = field(default_factory=list)  # v1 evidence lines
    fixed: bool | None = None  # None: no patched version to compare
    location: str = ""
    requirement_ids: list[str] = field(default_factory=list)

    @property
    def before_text(self) -> str:
        return self.evidence[0] if self.evidence else "Chỉ khai báo trong đặc tả"

    @property
    def after_text(self) -> str:
        if self.fixed is None:
            return "—"
        if self.fixed:
            return "; ".join(self.after) if self.after else "0 finding"
        return "CHƯA VÁ: " + "; ".join(self.after)


@dataclass
class SecurityAuditReport:
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    findings: list[CWEFinding] = field(default_factory=list)
    summary_text: str = ""

    @property
    def confirmed(self) -> list[CWEFinding]:
        return [f for f in self.findings if f.status == "confirmed"]

    @property
    def open_findings(self) -> list[CWEFinding]:
        """Confirmed findings that are not proven fixed by a patched version."""
        return [f for f in self.confirmed if f.fixed is not True]

    @property
    def declared_only(self) -> list[CWEFinding]:
        return [f for f in self.findings if f.status == "declared-only"]


CWE_KNOWLEDGE_BASE = {
    "buffer-overflow": {
        "id": "CWE-120", "name": "Buffer Copy without Checking Size of Input", "severity": "CRITICAL",
        "cve": "CVE-2021-3156 (Sudo Baron Samedit)",
        "desc": "Sao chép dữ liệu vào bộ đệm kích thước cố định mà không kiểm tra độ dài, cho phép ghi đè stack.",
        "fix": "Đo độ dài bằng strnlen và từ chối input vượt quá kích thước bộ đệm; không dùng strcpy.",
    },
    "double-free": {
        "id": "CWE-415", "name": "Double Free", "severity": "HIGH", "cve": "CVE-2019-11932 (WhatsApp)",
        "desc": "Giải phóng cùng một vùng nhớ heap hai lần, làm hỏng metadata của bộ cấp phát.",
        "fix": "Gán con trỏ về NULL ngay sau free(); quy định rõ chủ sở hữu (ownership) của vùng nhớ.",
    },
    "memory-leak": {
        "id": "CWE-401", "name": "Missing Release of Memory after Effective Lifetime", "severity": "MEDIUM",
        "cve": "CVE-2019-11478 (Linux SACK)",
        "desc": "Vùng nhớ cấp phát không được giải phóng trên mọi đường thoát, gây cạn kiệt bộ nhớ (DoS dài hạn).",
        "fix": "Đảm bảo mọi nhánh thoát (kể cả nhánh lỗi) đều gọi free().",
    },
    "use-after-free": {
        "id": "CWE-416", "name": "Use After Free", "severity": "CRITICAL", "cve": "CVE-2019-0708 (BlueKeep)",
        "desc": "Truy cập vùng nhớ sau khi đã giải phóng, có thể dẫn tới thực thi mã tùy ý.",
        "fix": "Không dùng con trỏ sau free(); gán NULL ngay sau khi giải phóng.",
    },
    "format-string": {
        "id": "CWE-134", "name": "Use of Externally-Controlled Format String", "severity": "HIGH",
        "cve": "CVE-2012-0809 (sudo)", "desc": "Chuỗi định dạng của printf lấy từ dữ liệu bên ngoài.",
        "fix": "Luôn dùng chuỗi định dạng hằng: printf(\"%s\", s).",
    },
    "gets": {
        "id": "CWE-242", "name": "Use of Inherently Dangerous Function", "severity": "HIGH",
        "cve": "CVE-1999-0061", "desc": "Dùng gets() không thể giới hạn độ dài.", "fix": "Dùng fgets().",
    },
    "malloc-unchecked": {
        "id": "CWE-690", "name": "Unchecked Return Value to NULL Pointer Dereference", "severity": "MEDIUM",
        "cve": "-", "desc": "Dùng kết quả malloc() mà không kiểm tra NULL.",
        "fix": "Kiểm tra con trỏ trả về trước khi sử dụng.",
    },
    "malloc-size-overflow": {
        "id": "CWE-680", "name": "Integer Overflow to Buffer Overflow", "severity": "MEDIUM", "cve": "-",
        "desc": "Kích thước cấp phát là tích có thể tràn số, dẫn tới cấp phát thiếu.",
        "fix": "Dùng calloc(n, size) hoặc kiểm tra tràn trước khi nhân.",
    },
    "integer-overflow": {
        "id": "CWE-190", "name": "Integer Overflow or Wraparound", "severity": "HIGH",
        "cve": "CVE-2018-10299 (BeautyChain BEC token)",
        "desc": "Phép tính số nguyên vượt miền int32 và bị wrap-around (ví dụ tổng tiền thành số âm).",
        "fix": "Kiểm tra a > INT_MAX - b trước khi cộng, hoặc dùng kiểu rộng hơn.",
    },
    "divide-by-zero": {
        "id": "CWE-369", "name": "Divide By Zero", "severity": "MEDIUM", "cve": "CVE-2020-1971",
        "desc": "Phép chia không kiểm tra mẫu số bằng 0, gây crash (DoS).",
        "fix": "Kiểm tra mẫu số khác 0 trước khi chia.",
    },
    "hardcoded-credential": {
        "id": "CWE-798", "name": "Use of Hard-coded Credentials", "severity": "CRITICAL",
        "cve": "CVE-2020-10148 (SolarWinds Orion auth bypass)",
        "desc": "Giá trị bí mật hardcode trong mã nguồn cho phép vượt qua xác thực.",
        "fix": "Bỏ nhánh bí mật; so khớp với bí mật cấu hình ngoài mã nguồn bằng hmac.compare_digest.",
    },
    "uncaught-exception": {
        "id": "CWE-248", "name": "Uncaught Exception", "severity": "MEDIUM", "cve": "-",
        "desc": "Ngoại lệ không được xử lý làm dừng chương trình.", "fix": "Kiểm tra đầu vào và xử lý ngoại lệ.",
    },
    "deadlock": {
        "id": "CWE-833", "name": "Deadlock", "severity": "HIGH", "cve": "CVE-2020-25692 (OpenLDAP)",
        "desc": "Trạng thái đạt được không có chuyển tiếp đi ra: hệ thống treo.",
        "fix": "Bổ sung chuyển tiếp thoát (timeout/đối soát) hoặc self-loop nếu là trạng thái kết thúc hợp lệ.",
    },
    "improper-locking": {
        "id": "CWE-667", "name": "Improper Locking", "severity": "HIGH", "cve": "CVE-2016-5195 (Dirty COW)",
        "desc": "Hai mệnh đề loại trừ lẫn nhau cùng đúng tại một trạng thái đạt được (liên quan CWE-362 race condition).",
        "fix": "Đồng bộ hóa bằng mutex/khóa nguyên tử; loại bỏ chuyển tiếp dẫn tới trạng thái xung đột.",
    },
    "protection-failure": {
        "id": "CWE-693", "name": "Protection Mechanism Failure", "severity": "HIGH", "cve": "-",
        "desc": "Một thuộc tính an toàn/sống còn (CTL) của đặc tả bị vi phạm.",
        "fix": "Sửa mô hình trạng thái theo phản ví dụ; bổ sung điều kiện chặn (guard) còn thiếu.",
    },
}

STATIC_RULE_KEY = {"dangerous-function": "buffer-overflow", "gets": "gets", "format-string": "format-string",
                   "malloc-unchecked": "malloc-unchecked", "malloc-size-overflow": "malloc-size-overflow",
                   "double-free": "double-free", "use-after-free": "use-after-free",
                   "memory-leak": "memory-leak"}
SANITIZER_KEY = {"stack-buffer-overflow": "buffer-overflow", "heap-buffer-overflow": "buffer-overflow",
                 "double-free": "double-free", "heap-use-after-free": "use-after-free",
                 "memory-leak": "memory-leak", "signed-integer-overflow": "integer-overflow",
                 "null-dereference": "malloc-unchecked"}
DECLARED_KEY = {"buffer-overflow": "buffer-overflow", "memory-leak": "memory-leak",
                "double-free": "double-free", "use-after-free": "use-after-free",
                "integer-overflow": "integer-overflow"}
FUZZ_KEY = {"ZeroDivisionError": "divide-by-zero", "bypass": "hardcoded-credential"}


class _Collector:
    def __init__(self, spec: Specification):
        self.spec = spec
        self.items: dict[tuple[str, str], CWEFinding] = {}

    def get(self, key: str, component: str, chapter: str, location: str = "") -> CWEFinding:
        k = (key, component)
        if k not in self.items:
            kb = CWE_KNOWLEDGE_BASE[key]
            reqs = [r.id for r in self.spec.requirements if component and component in r.text]
            self.items[k] = CWEFinding(kb["id"], kb["name"], kb["severity"], component, kb["desc"], kb["cve"],
                                       kb["fix"], chapter=chapter, location=location, requirement_ids=reqs)
        return self.items[k]

    @staticmethod
    def add_tool(f: CWEFinding, tool: str, evidence: str) -> None:
        if tool not in f.tools:
            f.tools.append(tool)
        if evidence not in f.evidence:
            f.evidence.append(evidence)


def analyze_security_vulnerabilities(
    spec: Specification,
    kripke_report: KripkeCheckReport | None = None,
    smt_results: list[SMTCheckResult] | None = None,
    *,
    functions: list[GeneratedFunction] | None = None,
    static: dict[tuple[str, str], list[Finding]] | None = None,
    sanitizers: list[SanitizerRun] | None = None,
    fuzz: list[FuzzResult] | None = None,
    bmc: list[BMCResult] | None = None,
) -> SecurityAuditReport:
    """Aggregate tool evidence into CWE findings.

    Analyses that were not passed in are computed cheaply here (static scan,
    small fuzzing budget) so the function also works stand-alone; sanitizer
    runs are only used when provided because they need a compiler.
    """
    functions = functions if functions is not None else generate_all_functions(spec)
    if static is None:
        static = {}
        for gf in functions:
            if gf.language == "c":
                static[(gf.spec.name, "v0")] = analyze_c_source(gf.code_vulnerable)
                static[(gf.spec.name, "v1")] = analyze_c_source(gf.code_safe)
    if fuzz is None:
        fuzz = [r for gf in functions for r in fuzz_generated(gf, budget=300, seed=1)]
    col = _Collector(spec)

    # --- Chương 1: Kripke / CTL / BMC ------------------------------------------------
    if kripke_report:
        for r in kripke_report.property_results:
            if r.passed or r.status == "error":
                continue
            trace = " -> ".join(r.counterexample_path) if r.counterexample_path else ", ".join(r.violation_states)
            if r.kind == "deadlock":
                f = col.get("deadlock", "Mô hình trạng thái", "Ch.1", ", ".join(r.violation_states))
                col.add_tool(f, "Kripke", f"Trạng thái deadlock: {', '.join(r.violation_states)}")
            elif r.kind == "mutex":
                f = col.get("improper-locking", r.formula, "Ch.1", ", ".join(r.violation_states))
                col.add_tool(f, "Kripke", f"{r.formula} sai; phản ví dụ: {trace}")
            else:
                f = col.get("protection-failure", r.formula, "Ch.1", ", ".join(r.violation_states))
                col.add_tool(f, "CTL", f"{r.formula} sai; phản ví dụ: {trace}")
    for b in bmc or []:
        if b.status != "unsafe":
            continue
        is_mutex = any(f.kind == "mutex" and f.formula == b.property
                       for f in (kripke_report.property_results if kripke_report else []))
        f = col.get("improper-locking" if is_mutex else "protection-failure", b.property, "Ch.3")
        col.add_tool(f, "BMC (Z3)", f"BMC SAT tại k={b.violation_depth}: {' -> '.join(b.counterexample)}")

    # --- Chương 2: static scanner + sanitizers ---------------------------------------
    by_name = {gf.spec.name: gf for gf in functions}
    for (name, version), findings in static.items():
        for fd in findings:
            key = STATIC_RULE_KEY[fd.rule]
            if version == "v0":
                f = col.get(key, name, "Ch.2", f"dòng {fd.line}")
                col.add_tool(f, "Static scanner", f"Scanner: {fd.rule} tại dòng {fd.line} (`{fd.code}`)")
    for run in sanitizers or []:
        for kind, _cwe, line in run.detections:
            key = SANITIZER_KEY.get(kind)
            if key is None or run.version != "v0":
                continue
            f = col.get(key, run.function, "Ch.2" if key != "integer-overflow" else "Ch.3",
                        f"dòng {line}" if line else "")
            col.add_tool(f, "ASan/UBSan", f"Sanitizer: {kind}" + (f" tại dòng {line}" if line else "")
                         + f" với input {run.input_desc}")

    # --- Chương 3: SMT ------------------------------------------------------------
    for smt in smt_results or []:
        if not smt.overflow_possible:
            continue
        f = col.get("integer-overflow", smt.name, "Ch.3")
        ev = f"Z3 SAT: {smt.overflow_values} → giá trị đúng {smt.overflow_evaluated}"
        if smt.bv_overflow:
            ev += f"; bit-vector 32-bit wrap-around = {smt.wrapped_value}"
        col.add_tool(f, "Z3", ev)
        if smt.patch_status != "n/a":
            f.fixed = smt.patch_status == "unsat"
            f.after.append(f"Z3 {smt.patch_status.upper()} với tiền điều kiện của v1")

    # --- Chương 4: fuzzing -----------------------------------------------------------
    for r in fuzz:
        if r.version != "v0" or not r.found:
            continue
        key = FUZZ_KEY.get(r.finding or "", "uncaught-exception")
        f = col.get(key, r.function, "Ch.4")
        col.add_tool(f, f"Fuzzing ({r.strategy})",
                     f"{r.strategy}: {r.finding} ở lần thử {r.first_hit}/{r.budget}, input {r.first_input}")

    # --- v1 evidence (after) --------------------------------------------------------
    for f in col.items.values():
        if f.chapter == "Ch.1" or (f.chapter == "Ch.3" and f.source_component not in by_name):
            continue
        name = f.source_component
        after: list[str] = []
        v1_static = [fd for fd in static.get((name, "v1"), []) if CWE_KNOWLEDGE_BASE[STATIC_RULE_KEY[fd.rule]]["id"] == f.cwe_id]
        if (name, "v1") in static:
            after.append(f"Scanner v1: {len(v1_static)} finding")
        v1_runs = [r for r in sanitizers or [] if r.function == name and r.version == "v1" and r.status != "skipped"]
        for r in v1_runs:
            after.append(f"Sanitizer v1: {'sạch' if r.status == 'clean' else r.status}")
        v1_fuzz = [r for r in fuzz if r.function == name and r.version == "v1"]
        for r in v1_fuzz:
            after.append(f"{r.strategy} v1: {r.hits}/{r.iterations} lỗi")
        if after:
            f.after = after + f.after
            f.fixed = not v1_static and all(r.status == "clean" for r in v1_runs) and not any(r.found for r in v1_fuzz)

    # --- declared but not reproduced ----------------------------------------------
    for fn in spec.functions:
        key = DECLARED_KEY.get(fn.bug or "")
        if key and (key, fn.name) not in col.items:
            f = col.get(key, fn.name, "Ch.2")
            f.status = "declared-only"
            f.evidence.append(f"Khai báo Loi='{fn.bug}' nhưng không công cụ nào xác nhận")

    findings = sorted(col.items.values(), key=lambda f: (f.status != "confirmed", f.chapter, f.cwe_id))
    counts = {s: sum(1 for f in findings if f.severity == s and f.status == "confirmed")
              for s in ("CRITICAL", "HIGH", "MEDIUM")}
    confirmed = [f for f in findings if f.status == "confirmed"]
    lines = [f"=== TỔNG HỢP LỖ HỔNG (dựa trên bằng chứng công cụ): {spec.name} ===",
             (f"Xác nhận bởi công cụ: {len(confirmed)} "
              f"(bản vá được xác minh: {sum(f.fixed is True for f in confirmed)}, "
              f"chưa vá: {sum(f.fixed is False for f in confirmed)}, "
              f"lỗi thiết kế mô hình: {sum(f.fixed is None for f in confirmed)}) | "
              f"Chỉ khai báo: {sum(f.status == 'declared-only' for f in findings)}"), ""]
    for i, f in enumerate(findings, 1):
        lines.append(f"{i}. [{f.severity}] {f.cwe_id} {f.cwe_name} — {f.source_component} ({f.status})")
        for e in f.evidence:
            lines.append(f"     v0: {e}")
        if f.fixed is not None:
            lines.append(f"     v1: {f.after_text}")
    return SecurityAuditReport(
        total_findings=sum(f.status == "confirmed" for f in findings),
        critical_count=counts["CRITICAL"], high_count=counts["HIGH"], medium_count=counts["MEDIUM"],
        findings=findings, summary_text="\n".join(lines),
    )
