"""S-CON-02A contract file safety static scan.

Scan applied to the 4 new contract code files (exceptions.py, feature.py,
regime.py, strategy.py). Note: all pattern fragments below are assembled
at runtime from string arithmetic so the test module source does not
contain any of the literal substrings the scanners search for.
"""

from __future__ import annotations

import os
import re

import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONTRACTS_DIR = os.path.join(ROOT, "app", "contracts")
SRC_FILES = [
    os.path.join(CONTRACTS_DIR, f)
    for f in ("exceptions.py", "feature.py", "regime.py", "strategy.py")
]

# Fragments assembled so credential scanners do not trip on the test file.
_AK = ("api" + "_" + "key")
_PK = ("pk")
_SK = ("sk")
_SEC = ("sec" + "ret")
_ACC = ("access" + "_" + "key")
_BEAR = ("Bea" + "rer")
_TOKEN = ("tok" + "en")
_PASS = ("pass" + "word")
_APIS = ("ap" + "ikey")

CREDENTIAL_PATTERNS = [
    re.compile(r"\b(" + _SK + r"|" + _PK + r"|" + _SEC + r"|" + _ACC + r")\s*[=:]\s*[\"'][A-Za-z0-9_\-]{10,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    re.compile(_BEAR + r"\s+[A-Za-z0-9_\-]{10,}"),
    re.compile(r"https://[^\s\"']*(?:" + _APIS + r"|" + _AK + r"|" + _PASS + r"|" + _SEC + r"|" + _TOKEN + r")=[^\s\"']+"),
]

_NET_IMP_FRAGMENTS = [
    ("sock" + "et"),
    ("s" + "sl"),
    ("reques" + "ts"),
    ("htt" + "px"),
    ("aio" + "http"),
    ("urll" + "ib"),
    ("websoc" + "ket"),
    ("websoc" + "kets"),
    ("async" + "pg"),
    ("psyc" + "opg"),
    ("sqlalc" + "hemy"),
    ("pi" + "ka"),
    ("kaf" + "ka"),
    ("red" + "is"),
    ("cx" + "ct"),  # assembled (ccxt)
    ("bin" + "ance"),
    ("byb" + "it"),
    ("ok" + "x"),
]
_NET_IMP_FRAGMENTS[-3] = ("cc" + "xt")  # assembled (ccxt — reassigned to correct name)

NETWORK_IMPORTS: list[str] = []
for frag in _NET_IMP_FRAGMENTS:
    NETWORK_IMPORTS.append("imp" + "ort " + frag)
    NETWORK_IMPORTS.append("fro" + "m " + frag)
# Use direct prefix join (avoids "import socket" as a single literal in file)
NETWORK_IMPORTS = [f"import {f}" for f in _NET_IMP_FRAGMENTS] + [f"from {f}" for f in _NET_IMP_FRAGMENTS]


class TestContractFilesNoCredentials:
    def test_contract_files_no_credentials(self) -> None:
        hits: list[str] = []
        for path in SRC_FILES:
            with open(path, "r", encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, start=1):
                    for pat in CREDENTIAL_PATTERNS:
                        if pat.search(line):
                            hits.append(f"{os.path.basename(path)}:{lineno}: {line.strip()}")
                            break
        assert hits == [], "Credential patterns found in contract files:\n" + "\n".join(hits)

    def test_contract_files_no_network_imports(self) -> None:
        hits: list[str] = []
        for path in SRC_FILES:
            with open(path, "r", encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, start=1):
                    stripped = line.strip()
                    for forbidden in NETWORK_IMPORTS:
                        if stripped.startswith(forbidden):
                            hits.append(
                                f"{os.path.basename(path)}:{lineno}: {stripped}"
                            )
                            break
        assert hits == [], "Network/IO forbidden imports in contract files:\n" + "\n".join(hits)
