"""Durable Ch.4 evidence and concrete replay, shared by the GUI and exporter."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .codegen import GeneratedFunction
from .fuzzing import FuzzResult, load_function, run_oracle

STOP_LABELS = {
    "not_started": "Chưa chạy",
    "budget_exhausted": "Hết ngân sách",
    "worklist_exhausted": "Hết worklist trong phạm vi hỗ trợ",
    "unsupported": "Chưa hỗ trợ cú pháp/thư viện — chưa đủ kết luận",
    "solver_unknown": "Solver chưa kết luận / timeout",
    "first_hit": "Dừng khi tìm thấy lỗi đầu tiên",
    "bounded_exploration_complete": "Duyệt xong trong giới hạn độ sâu và số lần lặp",
}


def result_label(result: FuzzResult) -> str:
    if result.found:
        return "TÌM THẤY LỖI"
    if result.status == "inconclusive":
        return "CHƯA ĐỦ KẾT LUẬN"
    return "CHƯA THẤY LỖI TRONG PHẠM VI CHẠY"


def code_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def replay_input(gf: GeneratedFunction, args: list[int] | tuple[int, ...]) -> list[dict]:
    """Replay the exact input on both generated variants; no symbolic assumptions are needed."""
    if len(args) != len(gf.spec.params) or any(type(v) is not int for v in args):
        raise ValueError("Input phải gồm đúng số tham số nguyên của hàm")
    results = []
    for version, code in (("v0", gf.code_vulnerable), ("v1", gf.code_safe)):
        outcome = run_oracle(load_function(code, gf.spec.name), gf.spec.kind.lower(), tuple(args))
        results.append({"function": gf.spec.name, "version": version, "input": list(args),
                        "code_sha256": code_hash(code), **asdict(outcome)})
    return results


def input_graph(result: FuzzResult) -> str:
    """A provenance graph, not a CFG or a proof that unexplored branches are safe."""
    lines = ['digraph inputs {', 'rankdir=LR;', 'node [shape=box];']
    for trial in result.trials:
        node = f"i{trial['iteration']}"
        label = f"#{trial['iteration']} input={trial['input']}\n{trial['finding'] or 'không lỗi'}"
        lines.append(f'{node} [label={json.dumps(label, ensure_ascii=False)}];')
        parent = trial.get("parent_iteration")
        if parent:
            label = trial.get("query_id") or trial.get("mutation", {}).get("operator", "mutation")
            lines.append(f'i{parent} -> {node} [label={json.dumps(label)}];')
    lines.append('}')
    return '\n'.join(lines)


def export_fuzz_evidence(report, out: Path) -> Path:
    """Every export creates an immutable-by-convention run folder; earlier runs are preserved."""
    run_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
    root = out / 'fuzz_runs' / run_id
    root.mkdir(parents=True)
    manifest = {"schema_version": 1, "run_id": run_id, "spec": report.spec.name,
                "exported_at": datetime.now(UTC).isoformat(), "environment": report.environment,
                "seed": report.seed, "budget": report.fuzz_budget,
                "spec_sha256": code_hash(json.dumps(asdict(report.spec), sort_keys=True, default=str)),
                "scope": "Generated Python functions; state exploration evaluates the specification model",
                "campaigns": []}

    def dump(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

    for index, result in enumerate(report.fuzz):
        campaign_id = f'{index:03}_{result.version}_{result.strategy}'
        folder = root / campaign_id
        folder.mkdir()
        gf = next(gf for gf in report.functions if gf.spec.name == result.function)
        code = gf.code_vulnerable if result.version == 'v0' else gf.code_safe
        details = {k: v for k, v in asdict(result).items()
                   if k not in {'events', 'trials', 'queries'} and not k.startswith('_')}
        details.update(function=result.function, code_sha256=code_hash(code),
                       unique_findings=result.unique_findings, oracle=gf.spec.kind,
                       input_domain='signed int32', seed_input=[1] * len(gf.spec.params),
                       verdict=result_label(result), stop_label=STOP_LABELS.get(result.stop_reason, result.stop_reason))
        dump(folder / 'campaign.json', details)
        (folder / 'target.py').write_text(code, encoding='utf-8')
        with (folder / 'events.jsonl').open('w', encoding='utf-8') as fh:
            # Persist causality: execution precedes queries generated from that execution.
            for trial in result.trials:
                fh.write(json.dumps({"event": "execution", **trial}, ensure_ascii=False, default=str) + '\n')
                for query in result.queries:
                    if query['iteration'] == trial['iteration']:
                        fh.write(json.dumps({"event": "solver", **query}, ensure_ascii=False) + '\n')
        dump(folder / 'corpus.json', [t for t in result.trials if t.get('kept_in_corpus')])
        dump(folder / 'crashes.json', [t for t in result.trials if t['finding']])
        dump(folder / 'coverage.json', {"kind": "line", "lines": sorted(result._covered),
                                       "history": [{"iteration": t['iteration'], "new_lines": t['new_lines']}
                                                   for t in result.trials]})
        (folder / 'inputs.dot').write_text(input_graph(result), encoding='utf-8')
        for query in result.queries:
            qdir = folder / 'queries'
            qdir.mkdir(exist_ok=True)
            (qdir / f"{query['id']}.smt2").write_text(query['smt2'], encoding='utf-8')
            dump(qdir / f"{query['id']}.json", query)
        manifest['campaigns'].append({"id": campaign_id, **details})
    dump(root / 'replay_results.json', report.fuzz_replays)
    dump(root / 'state_exploration.json', [asdict(r) for r in report.state_fuzz])
    dump(root / 'manifest.json', manifest)
    (out / 'fuzz_runs' / 'latest.txt').write_text(run_id + '\n', encoding='utf-8')
    return root
