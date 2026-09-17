from __future__ import annotations

import ast
import csv
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.registry.exceptions import (
    ERR_CAP5_DIRECT_MUTATION,
    ERR_CAP5_FSM_FORBIDDEN,
)

PATTERN_P1 = "P1_DIRECT_STATUS_ASSIGN"
PATTERN_P2 = "P2_NON_REGISTRY_REQUEST_TRANSITION"
PATTERN_P3 = "P3_WRITE_PRIMITIVES_OUTSIDE_REGISTRY"
PATTERN_P4 = "P4_FSM_CONSTRUCTOR_BYPASS"

HRC15_REASON = ERR_CAP5_DIRECT_MUTATION
HRC16_REASON = ERR_CAP5_FSM_FORBIDDEN
HRC17_REASON = ERR_CAP5_DIRECT_MUTATION
HRC18_REASON = ERR_CAP5_DIRECT_MUTATION


@dataclass
class BypassFinding:
    pattern_id: str
    hrc_ref: str
    reason_code: str
    filepath: str
    line_no: int
    col_offset: int
    snippet: str

    def to_csv_row(self) -> list[str]:
        return [
            self.pattern_id,
            self.hrc_ref,
            self.reason_code,
            self.filepath,
            str(self.line_no),
            str(self.col_offset),
            self.snippet,
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "hrc_ref": self.hrc_ref,
            "reason_code": self.reason_code,
            "filepath": self.filepath,
            "line_no": self.line_no,
            "col_offset": self.col_offset,
            "snippet": self.snippet,
        }


@dataclass
class BypassAuditResult:
    scanned_files: int = 0
    findings: list[BypassFinding] = field(default_factory=list)
    per_pattern_counts: dict[str, int] = field(default_factory=dict)
    csv_path: str = ""
    md_path: str = ""

    def summary_dict(self) -> dict[str, Any]:
        return {
            "scanned_files": self.scanned_files,
            "total_findings": len(self.findings),
            "per_pattern_counts": dict(self.per_pattern_counts),
            "csv_output_path": self.csv_path,
            "md_output_path": self.md_path,
            "findings": [f.to_dict() for f in self.findings],
        }


def _relpath(posix_path: str) -> str:
    norm = posix_path.replace("\\", "/")
    return norm


def _is_registry_scope(filepath: str) -> bool:
    rel = _relpath(filepath)
    return rel.startswith("app/registry/") or rel.startswith("app\\\\registry\\\\")


def _is_storage_py(filepath: str) -> bool:
    rel = _relpath(filepath)
    return rel.endswith("app/registry/storage.py") or rel.endswith("app\\\\registry\\\\storage.py")


def _get_snippet(source_lines: list[str], line_no: int) -> str:
    idx = line_no - 1
    if 0 <= idx < len(source_lines):
        return source_lines[idx].strip()
    return ""


def _is_mv_status_attr(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr == "status"
    return False


def _is_status_dict_key(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value == "status"
    return False


def _check_p1_assign(node: ast.Assign | ast.AugAssign, filepath: str, source_lines: list[str], findings: list[BypassFinding]) -> None:
    if _is_registry_scope(filepath):
        return
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, ast.AugAssign):
        targets = [node.target]
    for tgt in targets:
        direct_hit = False
        if isinstance(tgt, ast.Attribute) and tgt.attr == "status":
            direct_hit = True
        elif isinstance(tgt, ast.Subscript):
            sl = tgt.slice
            if isinstance(sl, ast.Index):
                sl = sl.value  # type: ignore[attr-defined]
            if _is_status_dict_key(sl):
                direct_hit = True
        if direct_hit:
            findings.append(BypassFinding(
                pattern_id=PATTERN_P1,
                hrc_ref="HRC15",
                reason_code=HRC15_REASON,
                filepath=filepath,
                line_no=node.lineno,
                col_offset=getattr(node, "col_offset", 0),
                snippet=_get_snippet(source_lines, node.lineno),
            ))


def _check_p1_setattr_call(node: ast.Call, filepath: str, source_lines: list[str], findings: list[BypassFinding]) -> None:
    if _is_registry_scope(filepath):
        return
    func = node.func
    is_setattr = False
    if isinstance(func, ast.Name) and func.id == "__setattr__":
        is_setattr = True
    elif isinstance(func, ast.Attribute) and func.attr == "__setattr__":
        is_setattr = True
    if not is_setattr:
        return
    if len(node.args) >= 1:
        name_arg = node.args[0]
        if isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str) and name_arg.value == "status":
            findings.append(BypassFinding(
                pattern_id=PATTERN_P1,
                hrc_ref="HRC15",
                reason_code=HRC15_REASON,
                filepath=filepath,
                line_no=node.lineno,
                col_offset=getattr(node, "col_offset", 0),
                snippet=_get_snippet(source_lines, node.lineno),
            ))


def _check_p2_request_transition(node: ast.Call, filepath: str, source_lines: list[str], findings: list[BypassFinding]) -> None:
    if _is_registry_scope(filepath):
        return
    func = node.func
    name = ""
    if isinstance(func, ast.Name):
        name = func.id
    elif isinstance(func, ast.Attribute):
        name = func.attr
    if name == "request_transition":
        findings.append(BypassFinding(
            pattern_id=PATTERN_P2,
            hrc_ref="HRC16",
            reason_code=HRC16_REASON,
            filepath=filepath,
            line_no=node.lineno,
            col_offset=getattr(node, "col_offset", 0),
            snippet=_get_snippet(source_lines, node.lineno),
        ))


def _path_contains_registry_artifacts(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return ".registry-artifacts" in node.value
    if isinstance(node, ast.JoinedStr):
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str) and ".registry-artifacts" in v.value:
                return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _path_contains_registry_artifacts(node.left) or _path_contains_registry_artifacts(node.right)
    return False


def _check_p3_write_primitives(node: ast.Call, filepath: str, source_lines: list[str], findings: list[BypassFinding]) -> None:
    if _is_registry_scope(filepath):
        return
    func = node.func
    primitive_hit = False
    path_arg_candidate: ast.AST | None = None

    if isinstance(func, ast.Name) and func.id == "open":
        if len(node.args) >= 1:
            path_arg_candidate = node.args[0]
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                mode = kw.value.value
                if "wb" in mode or "ab" in mode:
                    primitive_hit = True
        for i, arg in enumerate(node.args):
            if i == 1 and isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                mode = arg.value
                if "wb" in mode or "ab" in mode:
                    primitive_hit = True

    if isinstance(func, ast.Attribute):
        if func.attr in ("write_text", "write_bytes"):
            primitive_hit = True
            path_arg_candidate = func.value
        if func.attr in ("replace", "move"):
            if isinstance(func.value, ast.Name) and func.value.id in ("os", "shutil"):
                primitive_hit = True
                if len(node.args) >= 1:
                    path_arg_candidate = node.args[0]

    if not primitive_hit:
        return

    path_involved = False
    if path_arg_candidate is not None:
        path_involved = _path_contains_registry_artifacts(path_arg_candidate)
    if isinstance(func, ast.Attribute) and func.attr in ("write_text", "write_bytes") and isinstance(func.value, ast.Call):
        inner = func.value.func
        if isinstance(inner, ast.Attribute) and inner.attr in ("joinpath", "__truediv__"):
            path_involved = True
        if isinstance(inner, ast.Name) and inner.id == "Path":
            if len(func.value.args) >= 1:
                if _path_contains_registry_artifacts(func.value.args[0]):
                    path_involved = True

    if not path_involved:
        for kw in node.keywords:
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str) and ".registry-artifacts" in kw.value.value:
                path_involved = True
                break

    if path_involved or not path_arg_candidate:
        if isinstance(func, ast.Attribute) and func.attr in ("write_text", "write_bytes"):
            path_involved = True

    if path_involved:
        findings.append(BypassFinding(
            pattern_id=PATTERN_P3,
            hrc_ref="HRC18",
            reason_code=HRC18_REASON,
            filepath=filepath,
            line_no=node.lineno,
            col_offset=getattr(node, "col_offset", 0),
            snippet=_get_snippet(source_lines, node.lineno),
        ))


def _check_p4_modelversion_constructor(node: ast.Call, filepath: str, source_lines: list[str], findings: list[BypassFinding]) -> None:
    if _is_storage_py(filepath):
        return
    func = node.func
    is_mv_ctor = False
    if isinstance(func, ast.Name) and func.id == "ModelVersion":
        is_mv_ctor = True
    elif isinstance(func, ast.Attribute) and func.attr == "ModelVersion":
        is_mv_ctor = True
    if not is_mv_ctor:
        return
    has_status_kw = False
    for kw in node.keywords:
        if kw.arg == "status":
            has_status_kw = True
            break
    if has_status_kw:
        findings.append(BypassFinding(
            pattern_id=PATTERN_P4,
            hrc_ref="HRC17",
            reason_code=HRC17_REASON,
            filepath=filepath,
            line_no=node.lineno,
            col_offset=getattr(node, "col_offset", 0),
            snippet=_get_snippet(source_lines, node.lineno),
        ))


class BypassAuditVisitor(ast.NodeVisitor):
    def __init__(self, filepath: str, source_lines: list[str], findings: list[BypassFinding]) -> None:
        self.filepath = filepath
        self.source_lines = source_lines
        self.findings = findings

    def visit_Assign(self, node: ast.Assign) -> None:
        _check_p1_assign(node, self.filepath, self.source_lines, self.findings)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        _check_p1_assign(node, self.filepath, self.source_lines, self.findings)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        _check_p1_setattr_call(node, self.filepath, self.source_lines, self.findings)
        _check_p2_request_transition(node, self.filepath, self.source_lines, self.findings)
        _check_p3_write_primitives(node, self.filepath, self.source_lines, self.findings)
        _check_p4_modelversion_constructor(node, self.filepath, self.source_lines, self.findings)
        self.generic_visit(node)


def _walk_py_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(str(root)):
        for fn in filenames:
            if fn.endswith(".py"):
                result.append(Path(dirpath) / fn)
    result.sort()
    return result


def _to_posix_rel(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    return str(rel).replace("\\", "/")


def _write_csv(output_dir: Path, result: BypassAuditResult) -> Path:
    csv_path = output_dir / "cap5_bypass_audit.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pattern_id", "hrc_ref", "reason_code", "filepath", "line_no", "col_offset", "snippet"])
        for finding in result.findings:
            w.writerow(finding.to_csv_row())
    return csv_path


def _write_md(output_dir: Path, result: BypassAuditResult) -> Path:
    md_path = output_dir / "cap5_bypass_audit.md"
    lines: list[str] = []
    lines.append("# CAP5 Bypass Audit Report")
    lines.append("")
    lines.append(f"- Scanned files: **{result.scanned_files}**")
    lines.append(f"- Total findings: **{len(result.findings)}**")
    lines.append("")
    lines.append("## Per-Pattern Counts")
    lines.append("")
    lines.append("| Pattern | Count |")
    lines.append("|---------|-------|")
    for pid in [PATTERN_P1, PATTERN_P2, PATTERN_P3, PATTERN_P4]:
        lines.append(f"| {pid} | {result.per_pattern_counts.get(pid, 0)} |")
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    for f in result.findings:
        lines.append(f"- **{f.pattern_id}** ({f.hrc_ref}, `{f.reason_code}`) at `{f.filepath}:{f.line_no}`: `{f.snippet}`")
    lines.append("")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return md_path


def run_ast_scan(root_path: Path) -> dict[str, Any]:
    root = Path(root_path)
    if not root.is_absolute():
        root = Path.cwd() / root

    output_dir = root / ".proof-artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)

    app_root = root / "app"
    files = _walk_py_files(app_root if app_root.exists() else root)

    result = BypassAuditResult()
    result.scanned_files = len(files)
    all_findings: list[BypassFinding] = []

    for fpath in files:
        try:
            source = fpath.read_text(encoding="utf-8")
            source_lines = source.splitlines()
            tree = ast.parse(source, filename=str(fpath))
            rel = _to_posix_rel(fpath, root)
            visitor = BypassAuditVisitor(rel, source_lines, all_findings)
            visitor.visit(tree)
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue

    result.findings = all_findings
    counts: dict[str, int] = {PATTERN_P1: 0, PATTERN_P2: 0, PATTERN_P3: 0, PATTERN_P4: 0}
    for f in all_findings:
        counts[f.pattern_id] = counts.get(f.pattern_id, 0) + 1
    result.per_pattern_counts = counts

    csv_p = _write_csv(output_dir, result)
    md_p = _write_md(output_dir, result)
    result.csv_path = str(csv_p)
    result.md_path = str(md_p)

    return result.summary_dict()
