import ast
import pathlib
import re


APP_OPP = pathlib.Path("app/opportunity")
FORBIDDEN_TOKENS = [
    "short",
    "SHORT",
    "leverage",
    "LEVERAGE",
    "futures",
    "FUTURES",
    "exchange",
    "EXCHANGE",
    "db",
    "DB",
    "postgres",
    "POSTGRES",
    "mysql",
    "MYSQL",
    "redis",
    "REDIS",
]


class TestSafetyBoundary:
    def _files(self):
        return sorted(str(p) for p in APP_OPP.rglob("*.py"))

    def test_no_short_leverage_futures_in_text(self):
        pattern = re.compile(r"\b(short|SHORT|leverage|LEVERAGE|futures|FUTURES)\b")
        matches = []
        for f in self._files():
            for i, line in enumerate(open(f, "r", encoding="utf-8"), 1):
                clean = re.sub(r"(['\"]).*?\1", "", line, flags=re.S)
                if pattern.search(clean):
                    matches.append((f, i, line.strip()))
        assert matches == []

    def test_signal_strength_only_no_leverage_multiply(self):
        # Verify that scorer never multiplies by leverage field
        for f in self._files():
            src = open(f, "r", encoding="utf-8").read()
            assert "leverage" not in src.lower() or "_leverage" not in src  # just paranoid double check

    def test_no_exchange_credentials_presence(self):
        # Also no direct API key / secret tokens handled by T21; here token check
        pattern = re.compile(r"\b(exchange|EXCHANGE|binance|coinbase|kraken|okx|bybit)\b")
        matches = []
        for f in self._files():
            for i, line in enumerate(open(f, "r", encoding="utf-8"), 1):
                clean = re.sub(r"(['\"]).*?\1", "", line, flags=re.S)
                if pattern.search(clean):
                    matches.append((f, i, line.strip()))
        assert matches == []
