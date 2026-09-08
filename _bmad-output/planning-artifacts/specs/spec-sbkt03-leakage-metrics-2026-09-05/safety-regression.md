# safety-regression.md — S-BKT-03
## Safety & Backward Compat / Regression Requirements Checklist (IMP audit zorunlu)

### 1. CAP-1 Live/Replay Parity (Replay Clock Deterministik, real saat YOK)
- [ ] Backtest + leakage + metrics modules: `datetime.now(\|Instant.now(\|time.time(\|time.sleep(\|os.urandom(` → AST 0 HIT (6 patterns × P1-P5 modules)
- [ ] `run_mode \| source_type \| live_mode \| is_live` if/elif/Attribute access AST 0 HIT × 5 modules × 2 branches
- [ ] Any future timestamp via CLOCK INPUT dışı kaynak; input fixture epoch_max 2024 → all literals module ≤ 2024-12-31 (CAP-L03 literal pattern)
- [ ] Determinism 10×2 PASS (CAP-DET01)

### 2. CAP-2 Quality Flags Immutable / Read-Only
- [ ] `validate_quality` / `validate_position` / `validate_market` import or call → 0 count in S-BKT-03 P3/P4 + test files
- [ ] `setattr(QualityFlags` veya qf.stale = True gibi attribute mutation AST 0 HIT (pattern: `\.stale\s*=\s*True \| \.invalid\s*=\s*True`)

### 3. CAP-4 RiskGate → PaperOrder Zinciri
- [ ] Pipeline stage order: risk.evaluate gate_result.allowed BEFORE PaperOrder() constructor. AST order: `gate_result = .gate.evaluate(.*)` occur BEFORE `PaperOrder(` in same file L order (pipeline.py). Byte order unchanged
- [ ] 0 direct PaperOrder() without gate_result.allowed (new modules: leakage_asserts / metrics NEVER write PO)

### 4. Single Writer AD-7/13/24
- [ ] `Position(` new constructor AST match: ONLY inside `app/simulation/portfolio.py` (S-PTF single-writer). S-BKT-03 3 new prod files = 0 HIT.
- [ ] `Portfolio(` new constructor AST match: 0 in S-BKT-03 modules.
- [ ] `PaperOrder(` 0 in P3/P4 leakage/metrics (only pipeline L609).
- [ ] `apply_fill(` S-PTF PositionEngine method: 0 call P3/P4 outside pipeline order.

### 5. Hard Safety v1 (Spot Long Only, NO Real Execution)
- [ ] Short/Futures/Leverage forbidden: `side.SHORT` enum AST 0; `leverage > 1` literal > 1 in backtest; `futures` word 0 match.
- [ ] Network 14 patterns: `requests\|aiohttp\|httpx\|urllib\|socket.connect\|websocket\|WebSocket\|pika\|redis\|pymongo\|sqlalchemy\|psycopg\|kafka\|fastapi\|Flask` 0 match P3/P4/test.
- [ ] Credentials 6 patterns: `api_key\|secret_key\|private_key\|credentials\|token\|.env` 0 match P3/P4/test.
- [ ] Real execution: `ccxt\|binance\|bybit\|coinbase\|exchange_api` 0 match
- [ ] ML train 3 patterns: `.fit(\|.partial_fit(\|SGDRegressor\|optimizer` 0 match

### 6. Backward Regression (Test counts)
| Hikaye | Baseline PASS | Baseline SKIP | S-BKT-03 sonrası KORUNMALI |
|--------|---------------|---------------|----------------------------|
| S-RDH-01 | 68 | 0 | PASS unchanged |
| S-RDH-02 | 64 | 0 | PASS unchanged |
| S-PLN-01 | 42 | 0 | PASS unchanged |
| S-CON-02A | 104 | 0 | PASS unchanged |
| S-CON-02B | 273 | 0 | PASS unchanged |
| S-CON-02C | 93 | 0 | PASS unchanged |
| S-FEA-01 | 120 | 0 | PASS unchanged |
| S-REG-01 | 302 | 0 | PASS unchanged |
| S-STR-01 | 401 | 0 | PASS unchanged |
| S-OPP-01 | 611 | 1 | 611 PASS unchanged; 1 SKIP unchanged |
| S-RSK-01 | 233 | 0 | PASS unchanged |
| S-RSK-02 | 250 | 0 | PASS unchanged |
| S-PTR-01 | 365 | 0 | PASS unchanged |
| S-PTF-01 | 259 | 3 | 259 PASS / 3 SKIP unchanged |
| S-PTF-02 | 333 | 3 | 333 PASS / 3 SKIP unchanged |
| **S-BKT-01** | **222** | 0 | **222/222 unchanged** (ZORUNLU) |
| **S-BKT-02** | ≥552 PASS | 0 | ≥552 unchanged PASS; total ≥619 collected unchanged |
| Non-backtest tests (excl backtest folder) | 3631 | 5 | 3631 PASS / 5 SKIP unchanged |
| **TOPLAM** | **4405** | **5** | **≥4725 PASS / ≤5 SKIP / 0 FAIL HEDEF** |

### 7. Zero Dependencies
- [ ] `pyproject.toml` dependencies = [] unchanged (empty array, `dependencies = \[\]`)
- [ ] S-BKT-03 modules: stdlib imports (`decimal`, `hashlib`, `statistics`, `dataclasses`, `typing`, `json`, `math`, `collections` only). `import numpy/pandas/scipy/requests/pydantic/...` AST 0 HIT.
