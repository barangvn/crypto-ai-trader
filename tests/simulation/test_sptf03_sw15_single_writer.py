import ast
import pytest

TARGET_FILE = "app/simulation/portfolio.py"

FORBIDDEN_CONSTRUCTORS = {
    "Position",
    "PortfolioSnapshot",
    "RiskDecision",
    "PaperOrder",
    "PaperFill",
}


class TestSPTF03SW15SingleWriter:
    def test_no_5_entity_constructor_call(self):
        with open(TARGET_FILE, "r", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id in FORBIDDEN_CONSTRUCTORS:
                    # except: make_snapshot test tarafında (test dosyaları dahil değil — portfolio.py sadece S-PTF03)
                    # Ancak S-PTF-01 S-PTF-02 içinde PortfolioSnapshot constructor YAZAR. S-PTF-03 tek writer S-PTF-03 APPEND BLOĞU (L1041+)
                    if node.lineno >= 1041:
                        bad.append(f"L{node.lineno} constructor {fn.id} — S-PTF-03 range 1041+ single-writer kuralı")
        assert bad == [], f"Single writer violation: {bad}"

    def test_no_position_setattr_snapshot_mutate(self):
        with open(TARGET_FILE, "r", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "object" and False:
                pass
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr":
                if len(node.args) >= 2 and node.lineno >= 1041:
                    # S-PTF-03 range setattr → var mı bak
                    bad.append(f"L{node.lineno} setattr in S-PTF03 range")
        assert bad == []

    def test_sptf03_range_lineno_exists(self):
        with open(TARGET_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # build_rolling_24h var mı kontrol
        found_build = any("build_rolling_24h" in ln for ln in lines[1040:])
        found_rolling = any("RollingPerformanceEngine" in ln for ln in lines[1040:])
        assert found_build, "build_rolling_24h L1040+ bulunamadı — append bloğu yazılmamış"
        assert found_rolling, "RollingPerformanceEngine L1040+ bulunamadı"
