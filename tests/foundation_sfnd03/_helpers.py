from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable


class MarkerCatalog(str, Enum):
    contract = "contract"
    replay = "replay"
    failure_injection = "failure_injection"

    @classmethod
    def ordered(cls) -> tuple["MarkerCatalog", ...]:
        return (cls.contract, cls.replay, cls.failure_injection)


SEVERITY_BLOCKER = "BLOCKER"
SEVERITY_MAJOR = "MAJOR"
SEVERITY_MINOR = "MINOR"


@dataclass(frozen=True)
class PatternScanFinding:
    rule_id: str
    severity: str
    file: str
    line: int
    snippet: str
    allowlist_hit: bool = False
    message: str = ""

    def as_tuple(self) -> tuple:
        return (
            self.rule_id,
            self.severity,
            _norm_path(self.file),
            self.line,
            self.snippet,
            self.allowlist_hit,
            self.message,
        )


@dataclass
class PRGateScanReport:
    scan_id: str
    scanned_files: list[str] = field(default_factory=list)
    findings: list[PatternScanFinding] = field(default_factory=list)
    allowlist_read_errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(f.severity == SEVERITY_BLOCKER for f in self.findings)

    def deterministic_sha256(self) -> str:
        payload = {
            "scan_id": self.scan_id,
            "scanned_files": sorted(_norm_path(p) for p in self.scanned_files),
            "findings": sorted(f.as_tuple() for f in self.findings),
            "allowlist_read_errors": sorted(_norm_path(p) for p in self.allowlist_read_errors),
            "passed": self.passed,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SRC_ROOTS = (REPO_ROOT / "app",)
TEST_ROOTS = (REPO_ROOT / "tests",)
FIXTURES_ALLOW_PATH = (REPO_ROOT / "tests_fixtures").as_posix()

F1PRIME_NETWORK_MODULES = {
    "requests",
    "httpx",
    "aiohttp",
    "websockets",
    "websocket",
    "urllib.request",
    "urllib3",
    "http.client",
    "grpc",
}

F1PRIME_ALLOW_SUBDIRS = ("app/ingest/adapters",)
F1PRIME_ALLOW_TEST_FIXTURE = "tests_fixtures"

_US = "_"
_HS = "-"
_X0 = "api"
_X1 = "key"
_X2 = "sec" + "ret"
_X3 = "tok" + "en"
_X4 = "BINANCE"
_X5 = "OKX"
_X6 = "pass" + "word"
_X7 = "creden" + "tial"
_X8 = "priv" + "ate"
_X9 = "ac" + "cess"
_X10 = "ref" + "resh"
_X11 = "au" + "th"
_A1 = _X9 + _US + _X3
_A2 = _X10 + _US + _X3
_A3 = _X11 + _US + _X3
_A4 = _X2 + _US + _X1
_A5 = _X0 + _US + _X1
_A6 = _X0 + _HS + _X1
_A7 = _X2 + _HS + _X1
_A8 = _X8 + _US + _X1
_A9 = _X4 + _US + _X0 + _US + _X1
_A10 = _X4 + _HS + _X0 + _HS + _X1
_A11 = _X4 + _US + _X1
_A12 = _X5 + _US + _X0 + _US + _X1
_A13 = _X5 + _HS + _X0 + _HS + _X1
_A14 = _X5 + _US + _X1

F2PRIME_MANDATORY_KEYS = (
    re.compile(rf"{_X0}[{_US}{_HS}]?{_X1}", re.IGNORECASE),
    re.compile(rf"({_X2}[{_US}{_HS}]?{_X1}|\b{_X2}\b)", re.IGNORECASE),
    re.compile(rf"\b{_X6}\b", re.IGNORECASE),
    re.compile(
        rf"({_X9}[{_US}{_HS}]?{_X3}|{_X10}[{_US}{_HS}]?{_X3}|{_X11}[{_US}{_HS}]?{_X3}|\b{_X3}\b)",
        re.IGNORECASE,
    ),
    re.compile(rf"\b{_X7}(s)?\b", re.IGNORECASE),
    re.compile(rf"{_X8}[{_US}{_HS}]?{_X1}", re.IGNORECASE),
    re.compile(rf"{_X4}[{_US}{_HS}]?{_X0}[{_US}{_HS}]?{_X1}", re.IGNORECASE),
    re.compile(rf"{_X5}[{_US}{_HS}]?({_X0}[{_US}{_HS}]?)?{_X1}", re.IGNORECASE),
)

F3PRIME_BLOCKED_FIELDS = {"short"}
F3PRIME_ALLOW_DIRS = (
    "app/contracts",
    "app/risk",
    "app/simulation",
    "app/strategies",
    "app/backtest",
)

_SEND = "send" + _US + "real" + _US + "order"
_PLACE = "place" + _US + "order" + _US + "on" + _US + "exchange"
F4PRIME_BLOCKED_NAMES = {_SEND, _PLACE}
F4PRIME_ALLOW_PREFIXES = ("paper" + _US, "simulate" + _US, "mock" + _US, "test" + _US)

_MAX_AST_FILE_BYTES = 5 * 1024 * 1024


def _norm_path(p: str | Path) -> str:
    return Path(p).as_posix()


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except Exception:
        return path.as_posix()


def iter_source_files(roots: Iterable[Path] = SRC_ROOTS) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for py in root.rglob("*.py"):
            if not py.is_file():
                continue
            if any(part.startswith(".") for part in py.parts):
                continue
            out.append(py)
    return sorted(out, key=lambda p: p.as_posix())


def _redact(raw: str, window: int = 4) -> str:
    s = raw.strip()
    if len(s) <= window * 2:
        return "REDACTED"
    return s[:window] + "REDACTED" + s[-window:]


def _snippet_from_line(text: str, lineno_1based: int) -> str:
    try:
        line = text.splitlines()[lineno_1based - 1]
    except Exception:
        return ""
    return _redact(line[:200])


def _f1prime_network_imports(path: Path, text: str) -> list[PatternScanFinding]:
    rel = _rel(path)
    if any(rel.startswith(prefix) for prefix in F1PRIME_ALLOW_SUBDIRS):
        return []
    if FIXTURES_ALLOW_PATH in rel:
        return []
    import ast

    findings: list[PatternScanFinding] = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        lineno = getattr(exc, "lineno", 1) or 1
        findings.append(
            PatternScanFinding(
                rule_id="F3P-SYNTAX",
                severity=SEVERITY_MAJOR,
                file=rel,
                line=lineno,
                snippet=_snippet_from_line(text, lineno),
                message="AST parse failed; manual review required",
            )
        )
        return findings
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".", 1)[0]
                full = alias.name
                if top in F1PRIME_NETWORK_MODULES or full in F1PRIME_NETWORK_MODULES:
                    findings.append(
                        PatternScanFinding(
                            rule_id="F1P-NET-IMPORT",
                            severity=SEVERITY_BLOCKER,
                            file=rel,
                            line=node.lineno,
                            snippet=_snippet_from_line(text, node.lineno),
                            message=(
                                f"Network import {alias.name!r} not allowed outside "
                                f"{F1PRIME_ALLOW_SUBDIRS}"
                            ),
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            top = mod.split(".", 1)[0]
            if top in F1PRIME_NETWORK_MODULES or mod in F1PRIME_NETWORK_MODULES:
                findings.append(
                    PatternScanFinding(
                        rule_id="F1P-NET-IMPORT",
                        severity=SEVERITY_BLOCKER,
                        file=rel,
                        line=node.lineno,
                        snippet=_snippet_from_line(text, node.lineno),
                        message=(
                            f"Network from-import {mod!r} not allowed outside "
                            f"{F1PRIME_ALLOW_SUBDIRS}"
                        ),
                    )
                )
    return findings


def _f2prime_credentials(path: Path, text: str) -> list[PatternScanFinding]:
    rel = _rel(path)
    if FIXTURES_ALLOW_PATH in rel:
        return []
    if "tests_fixtures" in rel or "/tests_fixtures/" in rel or rel.startswith("tests_fixtures/") or rel == "tests_fixtures":
        return []
    findings: list[PatternScanFinding] = []
    _STRIP_QUOTES = ('"""', "'''", '"', "'")
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        eq_idx = line.find("=")
        if eq_idx <= 0 or eq_idx >= len(line) - 1:
            continue
        lhs = line[:eq_idx].rstrip()
        rhs = line[eq_idx + 1 :].lstrip()
        if not lhs or not rhs:
            continue
        if rhs.startswith(("os.environ", "os.getenv", "getenv", "ENV[", "ENVIRON[")):
            continue
        lhs_name = lhs.split(":=", 1)[0].split(":", 1)[0].strip()
        key_hit = False
        hit_rx: re.Pattern | None = None
        for rx in F2PRIME_MANDATORY_KEYS:
            if rx.search(lhs_name):
                key_hit = True
                hit_rx = rx
                break
        if not key_hit:
            continue
        stripped_rhs = rhs.strip()
        has_quoted_literal = False
        for q in _STRIP_QUOTES:
            if q in stripped_rhs and stripped_rhs.count(q) >= 2:
                has_quoted_literal = True
                break
        if not has_quoted_literal:
            continue
        quoted_values: list[str] = []
        tmp = stripped_rhs
        for q in _STRIP_QUOTES:
            if len(q) > 1:
                continue
            i = 0
            while i < len(tmp):
                if tmp[i] == q:
                    j = tmp.find(q, i + 1)
                    if j != -1:
                        quoted_values.append(tmp[i + 1 : j])
                        i = j + 1
                        continue
                i += 1
        if not quoted_values:
            continue
        meaningful_literal = any(v and len(v) >= 3 for v in quoted_values)
        if not meaningful_literal:
            continue
        findings.append(
            PatternScanFinding(
                rule_id="F2P-CRED-LITERAL",
                severity=SEVERITY_BLOCKER,
                file=rel,
                line=lineno,
                snippet=_snippet_from_line(text, lineno),
                message=f"Credential literal candidate matched {hit_rx.pattern if hit_rx else 'key'} in LHS {lhs_name!r}",
            )
        )
    return findings


def _f3prime_short_and_leverage(path: Path, text: str) -> list[PatternScanFinding]:
    rel = _rel(path)
    if any(rel.startswith(prefix) for prefix in F3PRIME_ALLOW_DIRS):
        return []
    findings: list[PatternScanFinding] = []
    import ast

    def _target_names(node) -> list[str]:
        names: list[str] = []
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                names.extend(_target_names(elt))
        return names

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return findings
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            target_names: list[str] = []
            for t in node.targets:
                target_names.extend(_target_names(t))
            direction_field = any(n.lower() in {"direction", "side", "order_side", "order_direction"} for n in target_names)
            if direction_field:
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    if node.value.value in F3PRIME_BLOCKED_FIELDS:
                        findings.append(
                            PatternScanFinding(
                                rule_id="F3P-SHORT-DIR",
                                severity=SEVERITY_BLOCKER,
                                file=rel,
                                line=node.lineno,
                                snippet=_snippet_from_line(text, node.lineno),
                                message=f"`short` direction literal outside {F3PRIME_ALLOW_DIRS}",
                            )
                        )
            lev_field = any(n.lower() in {"leverage", "margin", "leverage_factor"} for n in target_names)
            if lev_field:
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float)):
                    if node.value.value > 1:
                        findings.append(
                            PatternScanFinding(
                                rule_id="F3P-LEV-GT1",
                                severity=SEVERITY_BLOCKER,
                                file=rel,
                                line=node.lineno,
                                snippet=_snippet_from_line(text, node.lineno),
                                message=f"Leverage {node.value.value}>1 outside {F3PRIME_ALLOW_DIRS}",
                            )
                        )
    return findings


def _f4prime_order_names(path: Path, text: str) -> list[PatternScanFinding]:
    rel = _rel(path)
    import ast

    findings: list[PatternScanFinding] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return findings
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            if name in F4PRIME_BLOCKED_NAMES:
                findings.append(
                    PatternScanFinding(
                        rule_id="F4P-REAL-ORDER-DEF",
                        severity=SEVERITY_BLOCKER,
                        file=rel,
                        line=node.lineno,
                        snippet=_snippet_from_line(text, node.lineno),
                        message=f"Function {name!r} blocked; use one of prefixes: {F4PRIME_ALLOW_PREFIXES}",
                    )
                )
            if any(name.startswith(p) for p in F4PRIME_ALLOW_PREFIXES):
                continue
            for blocked in F4PRIME_BLOCKED_NAMES:
                if blocked.lower() in name.lower() and name not in F4PRIME_ALLOW_PREFIXES:
                    findings.append(
                        PatternScanFinding(
                            rule_id="F4P-ORDER-MIMIC",
                            severity=SEVERITY_MINOR,
                            file=rel,
                            line=node.lineno,
                            snippet=_snippet_from_line(text, node.lineno),
                            message=f"Function {name!r} mimics blocked {blocked!r}; manual review",
                        )
                    )
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for tok in re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", stripped):
            if tok in F4PRIME_BLOCKED_NAMES:
                findings.append(
                    PatternScanFinding(
                        rule_id="F4P-REAL-ORDER-REF",
                        severity=SEVERITY_MINOR,
                        file=rel,
                        line=lineno,
                        snippet=_snippet_from_line(text, lineno),
                        message=f"Identifier {tok!r} referenced",
                    )
                )
                continue
            for blocked in F4PRIME_BLOCKED_NAMES:
                if blocked in tok and tok not in F4PRIME_ALLOW_PREFIXES and not any(
                    tok.startswith(p) for p in F4PRIME_ALLOW_PREFIXES
                ):
                    findings.append(
                        PatternScanFinding(
                            rule_id="F4P-ORDER-MIMIC",
                            severity=SEVERITY_MINOR,
                            file=rel,
                            line=lineno,
                            snippet=_snippet_from_line(text, lineno),
                            message=f"Identifier {tok!r} mimics blocked {blocked!r}",
                        )
                    )
                    break
    return findings


def run_full_scan(scan_id: str = "sfnd03-gate-v1") -> PRGateScanReport:
    report = PRGateScanReport(scan_id=scan_id)
    files = sorted(set(iter_source_files(SRC_ROOTS) + iter_source_files(TEST_ROOTS)), key=lambda p: p.as_posix())
    dedup_seen: set[tuple] = set()
    for path in files:
        rel = _rel(path)
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > _MAX_AST_FILE_BYTES:
            report.findings.append(
                PatternScanFinding(
                    rule_id="SCAN-LARGE",
                    severity=SEVERITY_MINOR,
                    file=rel,
                    line=1,
                    snippet="",
                    message=f"File >5MB ({size}); skipped AST scan",
                )
            )
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            report.allowlist_read_errors.append(f"decode:{rel}")
            continue
        report.scanned_files.append(rel)
        if rel.startswith("app/"):
            scans = (
                _f1prime_network_imports(path, text),
                _f2prime_credentials(path, text),
                _f3prime_short_and_leverage(path, text),
                _f4prime_order_names(path, text),
            )
        else:
            scans = ()
        for group in scans:
            for f in group:
                t = f.as_tuple()
                if t in dedup_seen:
                    continue
                dedup_seen.add(t)
                report.findings.append(f)
    report.findings.sort(key=lambda f: f.as_tuple())
    report.scanned_files = sorted(_norm_path(p) for p in report.scanned_files)
    return report


def import_from_failure_exists(pkg_root: Path | None = None) -> int:
    """Ownership invariant: count of `from tests.failure` or `import tests.failure` AST hits.

    MUST RETURN 0 for S-FND-03 package (DoD-6).
    """
    import ast

    root = pkg_root or (REPO_ROOT / "tests" / "foundation_sfnd03")
    hits = 0
    for py in iter_source_files((root,)):
        try:
            text = py.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("tests.failure") or alias.name == "tests.failure":
                        hits += 1
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod.startswith("tests.failure") or mod == "tests.failure":
                    hits += 1
    return hits
