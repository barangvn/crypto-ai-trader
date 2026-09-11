STORY:
S-MDL-01 — ModelVersion CRUD + Evidence References (Model Lifecycle Registry Foundation)
Kaynak: [EPICS.md Epic 13](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L455-L457), [S-CON-02C §3.2-3.5](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/S-CON-02C-opportunityscore-modellifecycle-champion-challenger-canonical-contracts.md#L122-L303), [LIFECYCLE.md](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/LIFECYCLE.md)

DEPENDENCIES:
HARD (tamamlandı ✅):
- S-CON-02C: ModelVersion / ModelLifecycleStatus / ModelLifecycleTransition / ModelEvaluation / ChampionChallengerEvaluation canonical contracts (commit 2fbf986)
- S-PLN-01: InMemoryTypedEventBus publish/subscribe/correlation/causation/DLQ (commit 2f74506)
- S-BKT-01/02/03: Backtest/walk-forward/metrics artifacts (commits b6f5411 → bbade89 → fb1b8fb, HEAD)
- S-RSK-01/02: RiskDecision gate + decision audit (commits 2920521 + b1712ba)
- S-PTR-01 + S-PTF-01/02/03: Paper execution/fill + position/portfolio/24h performance (commits 43e82c5 → 12b1dfb → 8eb78a9 → 0d5515d)
SOFT:
- S-MDL-02/03/04 (evaluation/compare/promote/rollback — OOS)
- S-API-01/02/03/04 (registry API ucu — sonraki epic)

SOURCE-BACKED SCOPE:
- PRD FR-033–FR-041: governed lifecycle, registry id/version/train period/feature set/params/eval windows/metrics/approval status, predecessor rollback
- PRD FR-035: stage/min sample fail → reject + evidence
- PRD FR-036: registry history audit
- EPICS §CAP-5: status mutation SADECE `request_transition(...)` (LIFECYCLE.md state machine)
- S-CON-02C §3.2 20 ModelVersion field (16 required + 4 optional)
- ADN-10 EPICS Appendix C L506: artifact_uri storage default local filesystem
- AD-20 Determinism 10× idem
- AD-19 Fail-Closed invalid payload/transition → reject
- AD-7/13/24 Single Writer: Sadece Model Registry = ModelVersion/ModelLifecycleTransition writer
- 19/19 contracts tamam; bu hikâye contracts kullanır, DEĞİŞTİRMEZ.

MODEL CRUD:
CREATE (ModelRegistry.create_model_version(payload) → MV):
  - Required (S-CON-02C §2.4 L155-175 zorunlu ZORUNLU): model_id (lowercase snake_case non-empty), version (semver-like non-empty), model_family, purpose (ModelPurposeEnum = 5 değer: regime_classification / opportunity_scoring / probability_estimation / strategy_weighting / feature_importance), status, training_data_range start/end, walk_forward_run_ids list[str] (None YOK, empty OK), compatibility_ref.feature_version, artifact_uri non-empty, hyperparams flat dict None YOK, metrics_on_promotion flat dict None YOK, approval_refs list[str] None YOK empty OK, correlation_id ULID len≥8, causation_id ULID len≥8.
  - Optional nullable: oos_range, created_at, promoted_at, retired_at, author_ref.
  - Deterministic `model_version_id = ULID determinist: sha256(model_id + "|" + version) → 10 run AYNI`.
  - Duplicate (aynı model_id+version) → `RegistryError(VERSION_ALREADY_EXISTS, ...)`.
  - CREATE → `model_version_created.v1` publish (bus, corr/caus).
READ (get_model_version(model_id, version) → MV):
  - Storage .registry-artifacts/model_id/version/mv-<sha>.json var ise → strict dataclass constructor (contract __post_init__ validate).
  - YOK → `RegistryError(MODEL_VERSION_NOT_FOUND)`.
  - Corrupt JSON → `RegistryError(STORAGE_CORRUPT)`.
UPDATE (update_metadata(mv, patch={...}) → MV NEW):
  - İZİN VERİLEN YALNIZCA immutable DIŞI alanlar: author_ref, approval_refs APPEND-only, metrics_on_promotion read-write, artifact_uri update allowed, walk_forward_run_ids APPEND-only; hyperparams READ-ONLY CREATE sabit, model_id/version/status/training/compatibility READ-ONLY.
  - Status YALNIZ request_transition() -> update doğrudan SET STATUS RAISE (`ERR_DIRECT_STATUS_MUTATION_FORBIDDEN CAP-5`).
  - UPDATE → new sha, yeni storage mv-<sha>.json write; Eski mv saklanır (audit history).
LIST (list_model_versions(filter={}) → list[ModelVersion] + Deterministic order):
  - Filters SOURCE-BACKED 4 type: status (ModelLifecycleStatus), model_id exact, created_after Instant, purpose (ModelPurposeEnum). Kaynakta olmayan regime/extra filter — S-MDL-02 için OOS.
  - Sort KEYS ZORUNLU: model_id ASC (lowercase), version SemVer ASC (major.minor.patch lex numeric tuples), created_at DESC.
  - Empty list → [], none found.

STATUS/CAP-5 (S-CON-02C §2.5 L176-205, LIFECYCLE.md §Geçişler §Forbidden):
- Direct mutation: `mv.status = ModelLifecycleStatus.CHAMPION` → doğrudan assignment veya update payload status key → HARD ERROR RegistryError CAP-5_ERR_DIRECT_STATUS_MUTATION_FORBIDDEN; NO write; NO publish (S-CON-02C §51 CAP-5 + LIFECYCLE L10).
- request_transition(model_id, version, *, to_status, transition_command, evidence_refs=None, approval_refs=None, gate_decision_id=None, audit_note=None) → tuple[ModelVersion, ModelLifecycleTransition, Envelope*published?]:
  - from_status = current.status.
  - VALID FSM EDGES 9 izinli (S-CON-02C §2.5 L179-189 9 edge):
    T1 candidate→tested run_backtest_and_evaluate;
    T2 tested→paper deploy_to_paper_track;
    T3 paper→challenger promote_challenger_candidate;
    T4 challenger→champion promote_champion;
    T5 champion→retired retire_champion;
    T6 candidate→retired admin_retire;
    T7 tested→retired admin_retire;
    T8 paper→retired admin_retire;
    T9 challenger→retired admin_retire.
  - from_status==to_status → HARD RAISE FSM_NOOP (CON-02C §4.2 L262).
  - INVALID EDGE 7 forbidden + otomatik tersler (S-CON-02C §2.6 L196-204):
    F1 candidate→champion, F2 paper→champion, F3 tested→champion, F4 retired→*, F5 champion→challenger, F6 challenger→paper, F7 tested→candidate → RAISE RegistryError CAP-5_FSM_FORBIDDEN_TRANSITION(f"from={from_status} to={to_status}").
  - transition_command EMPTY → RAISE (CON-02C §4.2 L264).
  - Yeni status alan MV storage güncelle; HEMEN transition create; audit log append; SONRA publish `model_version_status_transitioned.v1` (corr=MV.corr, causation=transition_id).
  - Transition history = storage sub-path transitions/tx-<transition_id>.json; audit için LİSTELE (read_transition_history()).

EVIDENCE REFS (S-CON-02C + S-BKT 01/02/03 outputs):
DESTEK 4 ZORUNLU + 3 OPSIYONEL TYPES:
  ZORUNLU registry create/transition için min 1 evidence_refs:
  1. `historical_oos_eval` — ModelEvaluation.eval_id ref (S-CON-02C §3.3 L214 DatasetKindEnum historical_oos → metrics required keys 11)
  2. `walk_forward_run` — MV.walk_forward_run_ids list append entry (S-BKT-02 L n_fold config / MFR.result SHA — artifact_uri ref to local backtest run log/sha)
  3. `paper_replay_eval` — DatasetKindEnum paper_replay eval_id
  4. `artifact_package` — MV.artifact_uri storage sha match (ADN-10 local fs + mv-<sha>.json integrity)
  OPSIYONEL 3:
  5. `featureset_ref` (compatibility_ref.feature_version → determinism link)
  6. `hyperparams_snapshot` — hyperparams dict sha (create-time)
  7. `cost_injection_config` — S-BKT-02 cost overrides sha
Her Evidence canonical:
  evidence_ref = typed nested (S-CON-02C §4.1 evidence_refs list[str]):
    {
      "type": str ∈ {historical_oos_eval, walk_forward_run, paper_replay_eval, artifact_package, featureset_ref, hyperparams_snapshot, cost_injection_config},
      "ref_id": str (eval_id / run_id / artifact_sha / feature_version),
      "artifact_uri": str (local fs ADN-10 default),
      "integrity_sha256": str | None (S-BKT outputs require sha; optional otherwise),
      "source_created_ts": Instant,
      "correlation_id": str (MV.corr_id match)
    }
BKT 01/02/03 → EVIDENCE bağlantısı:
  - S-BKT-01: BacktestRunResult + RunCounts → historical_oos_eval ModelEvaluation dataset_kind=historical_oos; metrics 11 required keys from BacktestPerformanceSummaryV2 (return_pct = total_return_pct, max_drawdown_pct, sharpe, sortino, profit_factor, total_fees_quote, avg_slippage_bps = 0 if n/a, trade_count, regime_coverage_count, window_days, oos_flag True).
  - S-BKT-02: MFR.result → type=walk_forward_run run_id = MF fold SHA; artifact_uri=.bk-artifacts/mf-runs/<sha>/mfr-result.json; integrity_sha256=MF summary sha; append MV.walk_forward_run_ids.
  - S-BKT-03: leakage_asserts.py + metrics_compute.py summary → historical_oos_eval metrics_on_promotion append + walk_forward_run BKT-03 cross-fold SHA; integrity_sha leakage manifest SHA.

APPROVAL/ROLLBACK:
Foundation scope (S-MDL-01 sadece STORAGE/POINTER):
  - `approval_refs: list[str]` → CREATE empty OK, UPDATE append-only (gerçek approval document uri/gate decision id), REQUIRED T4 challenger→champion transition için len(approval_refs) >= 1 (ADN-08 min 1 insan onayı policy default).
  - `predecessor_model_ref: {model_id:str, version:str} | None` (MV nested field → registry storage; S-CON-02C model.py nested EK — T4 promote olduğunda predecessor = eski champion. Oluşturulurken candidate/trained/paper None).
  - ROLLBACK ALGORİTMASI + promote karşılaştırma = S-MDL-02/03/04 OOS (S-MDL-01 SADECE veri yapıları + pointer + storage).
SINIR:
  - S-MDL-01 İÇİNDE PROMOTİON THRESHOLD / ROLLBACK TRİGGER CALCULATE YOK.
  - S-MDL-02: ModelEvaluation build + compare 11 metric (FR-038)
  - S-MDL-03: Promotion gate pass/fail + approval min sample
  - S-MDL-04: Rollback predecessor switch + CAP-5 FSM edge (champion rollback → Yeni transition command: rollback_champion; CON 02C L252 transition_command listesinde rollback_champion var → edge champion → retired + sonra eski champion yeniden candidate → tested → paper → challenger → champion OLUMSUZ; bunun yerine LIFECYCLE rollback özel ADN → S-MDL-04 içinde.

LIST/FILTER:
Supported 4 filters SOURCE-BACKED:
  1. `status: ModelLifecycleStatus` (CON enum 6 değer)
  2. `model_id: str` (exact match, lowercase)
  3. `created_after: Instant` (MV.created_at >; None varsa skip)
  4. `purpose: ModelPurposeEnum` (5 değer)
Not supported (OOS S-MDL-02+): regime filter, author filter, keyword search, sort custom.
Deterministic SORT ZORUNLU (AD-20):
  1. `model_id` ASC (case-fold lowercase stable), 2. `version` ASC (semver -> (major:int, minor:int, patch:int, pre:str) tuple), 3. `created_at` DESC (newest first)
Return: list[ModelVersion]; empty filter = ALL (storage index from root listing; deterministic her sefer aynı order).

STORAGE (ADN-10 EPICS L506: artifact_uri default local filesystem — NO DB/network/objectstore SDK Stdlib):
- ROOT klasör: `.registry-artifacts/` (proje root, stdlib pathlib mkdir exist_ok, izin yoksa → STORAGE_WRITE_PERMISSION_FAIL fail-closed)
- Path pattern: `.registry-artifacts/models/{model_id.lower()}/{sanitize(version)}/mv-{mv_sha256_12hex}.json`
- mv_sha256 = ModelVersion.schema_sha256() (S-CON-02C §3.0 L75 pattern: to_sorted_dict sha256 hexdigest 12)
- CREATE:
  - Atomic: `.registry-artifacts/.tmp/{ulid_new}.json` yaz → fsync → rename HEDEF (Windows move atomic).
  - Klasör yoksa mkdir(parents=True).
  - Duplicate: list `.registry-artifacts/models/{mid}/{ver}/` içi 1+ dosya var ise (veya aynımid+ver MV listede → VERSION_ALREADY_EXISTS fail closed)
- READ: open(..., encoding=utf-8) → JSON parse → strict ModelVersion(**payload) __post_init__ ContractSchemaError varsa → STORAGE_CORRUPT_PAYLOAD_SCHEMA_FAIL (REJECT no partial)
- UPDATE (metadata):
  - Yeni MV sha → yeni mv-{newsha}.json write atomik → Eski dosya SAKLANIR (AD 07 audit history deletion YOK; soft link yok; listeleme READ LATEST = max sha created)
  - Hyperparams field → UPDATE denemesi → HYPERPARAMS_IMMUTABLE_AFTER_CREATE_ERR
- HISTORY (transition): `.registry-artifacts/models/{mid}/{ver}/transitions/{transition_id}.json` (ModelLifecycleTransition + occurred_at/audit_note)
- CORRUPTED:
  - JSON parse ValueError → STORAGE_CORRUPT_JSON_FAIL
  - Required 16 field EKSİK → STORAGE_INCOMPLETE_FIELD_ERR
  - model_id/version path value ile payload value mismatch → STORAGE_PATH_PAYLOAD_MISMATCH
- Missing artifact_uri (MV.artifact_uri içinde nesne YOK, ama MV mevcut) → NO DELETE MV; sadece warning info code ARTIFACT_NOT_FOUND_REFERENCE_WARN, ModelVersion hala read/list edilir (silinmez).
- Invalid payload: constructor ContractSchemaError → create/update FAIL; storage write YOK.

EVENT BUS (S-PLN-01 InMemoryTypedEventBus REUSE, typed event ad + corr/caus + DLQ + version min contract):
Typed Event: `model_version_status_transitioned.v1`
  Required 12 alan:
    1. envelope.event_id ULID
    2. envelope.event_type = "model_version_status_transitioned.v1"
    3. envelope.contract_version (1,0,0)
    4. envelope.correlation_id = MV.correlation_id  (ZORUNLU aynı)
    5. envelope.causation_id   = ModelLifecycleTransition.transition_id (parent)
    6. envelope.symbol = "*" (global registry, tekil event)
    7. envelope.source = "model_registry.v1"
    8. envelope.timestamp / ingest_ts = occurred_at / now_utc
    9. envelope.run_mode = source_type = clock_ref (aynı upstream envelope taşınır)
   10. payload:
       {
         "model_id": str,
         "version": str,
         "from_status": str (ModelLifecycleStatus.value),
         "to_status": str,
         "transition_command": str,
         "transition_id": str,
         "gate_decision_id": str | None,
         "mv_schema_sha256": str (new MV sha),
         "approval_count": int (len(approval_refs)),
         "occurred_at": Instant
       }
   11. envelope.quality_flags = UPSTREAM inherit (mutate YOK, CAP-2)
   12. envelope.schema_ref = "app/contracts/model.py:ModelLifecycleTransition+ModelVersion"
Publish Rules (ZORUNLU):
  - PUBLISH: SADECE VALID transition success (request_transition from/to valid edge; storage write OK; transition created)
  - NO PUBLISH: direct mutation denemesi, invalid transition FSM raise, duplicate MV, corrupt payload → HARD FAIL ANINDA; audit log local dosyaya `.registry-artifacts/logs/audit-YYYYMMDD.log` append; event bus publish YOK
  - Bus subscriber raise → AD-19: DLQ E_SUBSCRIBER_EXC; diğer subscriber OK devam (AD-19 isolation); transition kaydedildi (transactional öncelik: MV+transition storage WRITE SONRA publish; publish exception storage state rollback YOK — audit log ek)

DETERMINISM:
ZORUNLU 5 ADIM AD-20 10× AYNI OUTPUT:
1. ModelVersion deterministik: model_id + version → deterministic ulid_seed(sha256(model_id+version).digest(16)) → correlation_id/causation_id 10run AYNI
2. to_sorted_dict() — S-CON-02C §3.0 L74: alfabetik keys, Decimal→str, Enum→value, nested recursive
3. Evidence refs ordering: CREATE'deki list sırası KORUNUR (stable index); list evidence sort by type ASC then ref_id ASC (deterministic storage sırası)
4. Registry list() sort: model_id ASC / version semver tuples ASC / created_at DESC
5. Transition event payload sorted dict + publish ts = occurred_at FIXED deterministik (clock_ref deterministik verilirse 10run aynı event sha)
Assertion: 10 run same MV payload → schema_sha256() == 10 kez aynı; list() order aynı; transition_id deterministik same

FAIL-CLOSED (AD-19):
12 category invalid → RegistryError(reason_code, details) or CAP-5 / StorageError:
  A. CREATE payload 16 required eksik → MV_FIELD_MISSING_ERR
  B. CREATE/UPDATE invalid field (model_id UPPERCASE/boşluk/version non-semver-empty/purpose 5 dışı enum/status 6 dışı/training start>end/compat feature_version empty/artifact_uri empty/correlation causation <8)
  C. UPDATE HYPERPARAMS set attempt → HYPERPARAMS_IMMUTABLE_ERR
  D. UPDATE status DIRECT SET attempt → CAP5_DIRECT_STATUS_MUTATION_ERR
  E. request_transition FSM forbidden edge (F1-7) / noop (same) / empty command / retired from → CAP5_FSM_FORBIDDEN_TRANSITION / FSM_NOOP / COMMAND_EMPTY
  F. Duplicate CREATE same model_id+version → VERSION_ALREADY_EXISTS_ERR
  G. READ NOT FOUND → MODEL_VERSION_NOT_FOUND
  H. STORAGE: corrupt JSON / schema mismatch / path-payload mismatch / permission write denied / atomic rename fail → STORAGE_{CORRUPT,SCHEMA,MISMATCH,PERMISSION,ATOMIC}_FAIL
  I. Evidence integrity: integrity_sha beklenen mismatch → EVIDENCE_INTEGRITY_SHA_MISMATCH_REJECT (storage write NO)
  J. Transition approval_refs T4 promote_champion eksik → PROMOTE_MIN_APPROVAL_GATE_REJECT (ADN-08 min 1)
  K. Typed envelope 7 required positional (symbol/source/timestamp/ingest_ts/run_mode/source_type/clock_ref) missing → EVENT_ENVELOPE_FIELD_MISSING_ERR
  L. Artifact_uri YOK (mv oluşturma denemesi artifact_uri empty): denir ki → ARTIFACT_URI_REQUIRED_ERR (required MV field)
No silent success: ANY catch RegistryError raised or StorageError → RAISE or return Result(err) bool success=False, call try-except with audit.

SAFETY:
V1 HARD BOUNDARY 11 AD (BÜTÜN STORY HİSSİ — AST 0 match stdlib):
1. No exchange / No REST/HTTP / No urllib / No httpx / No requests / No WebSocket / No ccxt/binance SDK → AST forbidden imports 0 match
2. No API key / secret / credential literal (`api_key` `secret_key` `access_token`) regex scan → 0
3. No sqlite / sqlalchemy / asyncpg / redis → DB 0
4. No live trading / No real-order place_order/send_order/submit_order function names AST → 0
5. No Short: LimitsSnapshot.max_leverage_allowed UPSTREAM, contract side Enum Yalnızca long/flat → no SHORT_OPEN field
6. Leverage>1: LimitsSnapshot contract enforced upstream; story input limits enforce None or 1
7. No Futures: OrderType/FillType ENUM futures alanı YOK
8. No execution authority (AD-10): Registry NEVER PaperOrder/PaperFill üretir; sadece lifecycle metadata; risk/execution YOK
9. stdlib-only (pyproject dependencies=[]): imports sadece dataclasses / enum / decimal / re / hashlib / json / datetime / pathlib / shutil / os (stdlib) — S-CON-02C pattern AYNEN
10. No ML training / inference: bu hikâyede SADECE registry POINTER; AI model predict/fit/predict_proba çağrısı YOK
11. No time.sleep / no system clock wait: created_at ya input ya deterministic ClockRef (no real drift)

REUSE MAP:
REUSE (source-backed dosyalar + public import):
  - [app/contracts/model.py](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/app/contracts/model.py): ModelVersion / ModelLifecycleStatus / ModelPurposeEnum / TrainingDataRange / ModelCompatibilityRef / ModelEvaluation / ModelLifecycleTransition / ChampionChallengerEvaluation / PromotionGateResult  — S-CON-02C §3.2-5
  - app/platform/event_bus.py: InMemoryTypedEventBus subscribe_typed / publish_with_causation / trace_causation_chain / DLQ + contract_version_min
  - app/backtest/: (S-BKT 01/02/03 outputs): BacktestRunResult, MFResult, BacktestPerformanceSummaryV2, MetricsCompute helpers → evaluation/evidence bridge
  - app/contracts/types.py + exceptions.py: ULID/Instant/Symbol/format helpers + ContractSchemaError (registry exception extend etme — stdlib subclass)
  - to_sorted_dict + schema_sha256 helpers app/contracts/__init__.py (export: S-CON-02B önceden ekli)
  - AD-20 Determinism existing patterns: ULID deterministik seeding to_sorted_dict sort_keys
  - AD-19 Fail-Closed patterns: S-RSK-02 gate denemeleri pattern
DO NOT REIMPLEMENT (VAR OLAN KOD / CONTRACT KULLAN, TEKRAR YAZMA):
  - Backtest metrics (Sharpe/Sortino/PF/DD): S-BKT-03 metrics_compute + runner V2
  - PnL / cost: S-PTR + S-PTF
  - Portfolio / Position / 24h performance: S-PTF
  - Cost / fill models: S-BKT 02 / S-PTR
  - Risk decision engine: S-RSK 01/02
  - Strategy / Feature / Regime engine: S-STR / S-FEA / S-REG
  - Live data / replay normalizer / quality: S-RDH
  - CAP-5 forbidden transition contract-level validation → CON 02C ModelLifecycleTransition __post_init__; registry tekrar yazmaz, contract raise reuse eder
  - Champion challenger eval / rollback algorithm: S-MDL-02/03/04 (OOS)

HARD-RED (0 byte diff — değiştirilmeyecek/ dokunulmayacak klasör/dosyalar; sadece registry/contract import ET):
  1. app/contracts/ — Sadece read; YENİ contract YOK, mevcut public import korunur, dataclass field/sira DEGISMEZ (CONTRACT_VERSION 1.0.0 sabit)
  2. app/replay + replay bundle (S-RDH 01/02)
  3. app/platform/event_bus.py — S-PLN 01 YALNIZ publish/subscribe API KULLAN, implementasyon DEGISMEZ
  4. app/features (engine + feature compute)
  5. app/regime (MarketRegime detector)
  6. app/strategies (Trend/Momentum + strategy_context)
  7. app/opportunity (OpportunityScore score engine)
  8. app/risk (RiskEngine + gate enforcement + kill switch)
  9. app/simulation (execution fill / portfolio sim)
  10. app/backtest: ordering.py + pipeline.py HARD RED (bkt 02/03 specs), cost_injection + walk_forward + multi_fold_runner + runner + leakage_asserts + metrics_compute okunur, DEGISMEZ
  11. pyproject.toml: dependencies=[] EMPTY SABİT

AC COUNT:
Total 264 AC %100 test edilebilir, 22 Grup:
  G1. CREATE 16 required field PASS: 16
  G2. CREATE invalid 12 payload FAIL closed: 12
  G3. READ happy/notfound/corrupt: 12
  G4. UPDATE metadata allowed + immutable denemesi reject: 16
  G5. CAP-5 direct status mutation → 8 senaryo HARD FAIL: 8
  G6. request_transition VALID 9 edge PASS: 9
  G7. request_transition INVALID 7 forbidden + noop + empty command: 9
  G8. transition event + publish 9 senaryo: 9
  G9. DLQ/subscriber exc isolation AD-19: 5
  G10. Evidence types 7 create integrity SHA + ref validate: 21
  G11. BKT-01/02/03 → evidence linkage: 3*4=12 (her BKT için 4 ref type 3 evidence)
  G12. LIST 4 filter types + 3 sort order key inv: 4*3=12
  G13. Determinism: 5 fixtures × 10 run idem = 10 assert × 2 (sha + order) = 20
  G14. Storage: atomic create / rename / corrupt / duplicate / permission: 15
  G15. approval_refs min 1 T4 / predecessor create/populate: 10
  G16. Transition history listele: 8
  G17. Artifact_uri 11 requirement / missing warn NO delete: 6
  G18. Stdlib-only / dependencies=[] 0 deps AST 5: 5
  G19. Safety 11 boundary AST zero-match: 11
  G20. Hard-red 11 modül 0 değişim: 11
  G21. Corr/Caus chain 4 assert: 4
  G22. Regression: 4802 PASS+1 = 4803+ korunur: 6 (SBKT01/02/03 + SBKT01 total + SBKT02 total + SBKT03 total)
TOPLAM = 16+12+12+16+8+9+9+9+5+21+12+12+20+15+10+8+6+5+11+11+4+6 = 264.

DoD COUNT:
28/28 DoD (kaynak pattern S-PTR-01 AYNI, DoD-1..28 aşağı):
DoD1-6:  G1 Regression 6 PASS korunur
DoD7:    G2 12 invalid create FAIL closed 12/12
DoD8:    G3 READ happy/nf/corrupt 12/12
DoD9:    G4 UPDATE allowed vs immutable FAIL 16/16
DoD10:   G5 CAP-5 direct mutate FAIL 8/8
DoD11:   G6 Valid FSM edge 9 PASS + G7 Invalid FAIL 9 PASS = 18/18
DoD12:   G11 BKT 01/02/03 evidence linkage 12/12
DoD13:   G10 Evidence integrity 21/21
DoD14:   G9 Event publish / DLQ isolation 14/14
DoD15:   G12 Filter 4 × sort 3 = 12
DoD16:   G8 Valid Transition event typed 9/9
DoD17:   CAP-2 quality_flags YOK mutate / validator recall 0 import check 8 PASS
DoD18:   CAP-1 no run_mode/source_type branch AST scan 6 PASS
DoD19:   G1 fail closed matrix (A-L 12 kategori) 30 parametrize × 2 assert = 60/60
DoD20:   G13 Determinism 10× 20/20
DoD21:   G18 5 stdlib deps 5/5
DoD22:   Safety G19 11 AST 11/11
DoD23:   G14 Storage 15/15
DoD24:   Corr/caus G21 4/4
DoD25:   Hard-red 11 module diff 0 byte 11/11
DoD26:   TOPLAM yeni test ≥260 collect ve PASS. Full suite ≥4803 collected (prev 4802 + 1 new story)
DoD27:   Determinism 10x 14 fixtures × 2 sides (14 idem)
DoD28:   Contracts backward: getattr(app.contracts.model, "ModelVersion") çalışır; getattr(MV, "status") public attr preserved 3/3 pass
TOPLAM 28/28.

TEST TARGET:
Minimum ≥260 yeni test (S-MDL-01 spesifik), 32 kategorili, 2 test conftest.py (app registry + storage temp fixture) + 22 test dosyası:
  tests/registry/
    test_smdl01_01_create_required.py (16+12)
    test_smdl01_02_read_pathways.py (12)
    test_smdl01_03_update_immutable_guard.py (16)
    test_smdl01_04_cap5_direct_status.py (8)
    test_smdl01_05_transition_valid_9edges.py (9)
    test_smdl01_06_transition_invalid_forbidden.py (9)
    test_smdl01_07_transition_event_publish.py (9)
    test_smdl01_08_eventbus_dlq_isolation.py (5)
    test_smdl01_09_evidence_refs_integrity.py (21)
    test_smdl01_10_evidence_link_backtest.py (12)
    test_smdl01_11_list_filter_4types.py (12)
    test_smdl01_12_determinism_10x.py (20)
    test_smdl01_13_storage_atomic_corrupt.py (15)
    test_smdl01_14_approval_min_gate.py (10)
    test_smdl01_15_transition_history_audit.py (8)
    test_smdl01_16_artifact_required_missing.py (6)
    test_smdl01_17_stdlib_only.py (5)
    test_smdl01_18_safety_boundary_ast.py (11)
    test_smdl01_19_hardred_zerodiff.py (11)
    test_smdl01_20_corr_caus_chain.py (4)
    test_smdl01_21_regression_protect.py (6)
    test_smdl01_22_predecessor_pointer.py (ek)
    test_smdl01_23_invalid_payload_12category_matrix.py (30 parametrize)
    test_smdl01_24_event_correlation.py (ek)
TOPLAM ≥ 260 test cell.

OPEN DECISIONS (GERÇEK source-backed; KAYNAKTA AÇIK OLANLAR — tahmin YOK):
  OD-01. Predecessor ref relation cardinality: 1 champion 1 eski champion (single predecessor), ya N (tarihsel zincir)? — S-MDL-04 rollback ihtiyacına göre çözülür, bu hikâyede field NONE + allow 1 (ADN olarak bırakılır).
  OD-02. Evidence ref REPLACE vs APPEND: Update()'de walk_forward_run_ids APPEND-only mi ya da silebilir mi? (default ADN policy: APPEND-only; create edilen hyperparams/ model_id degismez; diğer evidence append-only. S-MDL-02 icin override ADN ile)
  OD-03. Storage hard delete mi vs soft tombstone? (ADN-13 tek writer: sadece CREATE/UPDATE/READ; DELETE → OOS S-MDL-05 (admin) sonraya; şu an No Delete)
  OD-04. Storage concurrent write atomicity (Win/Linux): Pathlib rename atomic mi? (default policy: tmp dosyası + rename; concurrent 2 yazarsa 2. yazan VERSION_ALREADY_EXISTS; LOCK YOK, fail atomically)
  OD-05. approval_refs minimum required: 1 insan (ADN-08: human approval şart policy default). Promotion T4 için. Test min=1; other transitions 0 allowed → APPEND-only.
  OD-06. UPDATE `metrics_on_promotion`: overwrite allowed or append only? (Default ADN: overwrite OK, çünkü metrics post-evaluation güncellenir. Hyperparams/feature/compat NOT)
  OD-07. Event retry on publish exception: bus publish fail → retry? (AD-19: DLQ; NO retry, audit log append, storage state commit korunur. Retry S-API/eventual için OOS.)
  OD-08. walk_forward_run_ids max entries: sınır 100 mü? Yoksa 0..N (ADN: max=250, overflow → WARNING info code, liste memory limiti). Default ADN S-MDL-01 icin 0..250.
  OD-09. duplicate version: create → HARD fail. force (admin) overwrite allowed → OOS.
  OD-10. oos_range / author_ref optional fields: update ile populate allowed? YES (not immutable read-only list; not in blocked list).

EXPECTED FILE CHANGES (APPEND-MODE ONLY, GERİYE DÖNÜŞ BOZULMAZ):
PRODUCTION (2+ YENİ DOSYA + 2 import append):
  1. app/registry/__init__.py           YENİ: ModelRegistry / RegistryError / EvidenceRef / DEFAULT_ROOT_PATH export
  2. app/registry/storage.py           YENİ: LocalFSRegistryStorage (ADN-10 local filesystem)
  3. app/registry/registry.py          YENİ: ModelRegistry (CRUD, request_transition, list, transition_history)
  4. app/__init__.py                    SONUNA EK: `from app import registry` (ops, import chain korunur)
  5. app/registry/events.py             YENİ: `model_version_status_transitioned.v1` build envelope helper
  6. app/registry/exceptions.py         YENİ: RegistryError / StorageError reason codes
TEST (22+ DOSYA, yeni tests/registry dizin):
  22 test_smdl01_*.py (yukarıda list) + tests/registry/conftest.py = 23 yeni test
SPEC (1 folder 6 md):
  Bu SPEC.md + companions: acceptance-criteria.md, dod.md, expected-file-changes.md, hard-red.md, reuse-map.md, open-decisions.md, safety-regression.md
TOPLAM 6 production / 23 test / 7 spec companions.

S-MDL-01 SPEC READY
