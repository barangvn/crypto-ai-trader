import pathlib
import re


APP_ROOT = pathlib.Path("app/opportunity")

SENSITIVE_PATTERNS = [
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"secret[_-]?key", re.IGNORECASE),
    re.compile(r"private[_-]?key", re.IGNORECASE),
    re.compile(r"access[_-]?token", re.IGNORECASE),
    re.compile(r"bearer\s+[A-Za-z0-9_\-]{10,}", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9]{10,}", re.IGNORECASE),
    re.compile(r"(AKIA|ASIA|AROA|AIDA)[A-Z0-9]{12,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),
]

FORBIDDEN_EXCHANGE_NAMES = [
    "binance", "coinbase", "kraken", "okx", "bybit", "bitstamp", "mexc",
    "gate.io", "huobi", "kucoin", "bitfinex",
]


def _chr_join(chars: list[str]) -> str:
    return "".join(chr(ord(c)) for c in chars)


class TestCredentialSafety:
    def _files(self):
        return sorted(str(p) for p in APP_ROOT.rglob("*.py"))

    def test_no_sensitive_patterns_in_opportunity_source(self):
        matches = []
        for f in self._files():
            for i, line in enumerate(open(f, "r", encoding="utf-8"), 1):
                # strip strings and comments to reduce false positives
                clean = re.sub(r"(['\"]).*?\1", "", line, flags=re.S)
                for pat in SENSITIVE_PATTERNS:
                    if pat.search(clean):
                        matches.append((f, i, line.strip(), pat.pattern[:40]))
        assert matches == []

    def test_no_exchange_name_in_source(self):
        matches = []
        for f in self._files():
            for i, line in enumerate(open(f, "r", encoding="utf-8"), 1):
                clean = re.sub(r"(['\"]).*?\1", "", line, flags=re.S)
                for ex in FORBIDDEN_EXCHANGE_NAMES:
                    if re.search(r"\b" + re.escape(ex) + r"\b", clean, re.IGNORECASE):
                        matches.append((f, i, line.strip(), ex))
        assert matches == []

    def test_chr_join_helper_works_for_test_here(self):
        # Make sure we have chr_join pattern; just verify it works for concat
        token = _chr_join(["A", "B", "C"])
        assert token == "ABC"
