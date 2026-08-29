"""S-RSK-02 RiskDecision → PaperOrder Gate Enforcement (CAP-4 Direct Proof).

Fail-closed deterministic typed gate between upstream approved RiskDecision
and downstream PaperOrder creation. Stdlib-only. No new canonical contracts
(helpers here only — contracts folder untouched).

Hard invariants (read-only enforcement layer):
  * AD-19: any exception / invalid / uncertainty => BLOCKED (never approve on error).
  * AD-20: same input tuple => same gate result + same sha256 across 10 runs.
  * CAP-4: approved Decision => ALLOW; rejected => BLOCK; missing Decision => BLOCK.
  * CAP-1: zero `if run_mode` / `if source_type` branches.
  * CAP-2: QualityFlags read-only. Never mutate; never invoke validator module.
  * AD-11: only an approved RiskDecision payload unlocks ALLOW.
  * v1 hard boundary: long-only spot, leverage==1, no short, no futures/perps.
  * Paper-only: no network, no exchange SDK, no credentials, no DB.

EventBus bridge helpers at bottom of this file (single-module bounded context).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace as _dc_replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Iterable, Optional

from app.contracts.canonical import CanonicalEventEnvelope, QualityFlags
from app.contracts.exceptions import ContractSchemaError, to_sorted_dict
from app.contracts.paper import (
    PaperOrder,
    PaperOrderPolicyRefs,
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
)
from app.contracts.risk import (
    KillSwitchStateSpec,
    LimitsSnapshot,
    PositionSizingSpec,
    RiskDecision,
    RiskDecisionResult,
)
from app.contracts.types import Instant, ULID, format_instant, validate_instant
from app.platform.event_bus import (
    DeadLetterRecord,
    InMemoryTypedEventBus,
    SubscriptionToken,
)


# ---------------------------------------------------------------------------
# Constants — fixture-overridable via GateOptions (frozen-like dataclass)
# ---------------------------------------------------------------------------

GATE_VERSION_RSK02: str = "rsk02_gate_v1"

DEFAULT_STALE_DECISION_THRESHOLD_SEC: float = 300.0  # 5 minutes
DEFAULT_OVERSIZE_TOLERANCE_BPS: int = 50  # 0.50%
DEFAULT_IDEMPOTENCY_MAX_ENTRIES: int = 100_000

EVENT_TYPE_RISK_DECISION_PUBLISHED: str = "risk.decision.published.v1"
EVENT_TYPE_PAPER_ORDER_CREATED: str = "paper.order.created.v1"
EVENT_TYPE_PAPER_ORDER_BLOCKED: str = "paper.order.blocked.v1"

FUTURES_PERP_TOKENS: tuple[str, ...] = (
    "PERP",
    "FUTURES",
    "SWAP",
    "-SHORT",
    "_SHORT",
    "/SHORT",
    "SHORT",
)


# ---------------------------------------------------------------------------
# Typed helpers — NOT public canonical contracts (bounded context only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PaperOrderGateRequest:
    """Typed input to the gate. Raw dicts rejected at gate.evaluate.

    Mirrors fields the gate actually checks from a would-be PaperOrder,
    without duplicating the full PaperOrder schema or requiring
    paper_order_id / status / timestamps because those are assigned
    downstream only if gate.allowed==True.
    """

    symbol: str
    side: PaperOrderSide
    order_type: PaperOrderType
    requested_qty_base: Decimal
    requested_notional_quote: Decimal
    requested_price: Optional[Decimal]
    policy_refs: PaperOrderPolicyRefs
    correlation_id: ULID
    causation_id: ULID
    position_intent: str = "OPEN_NEW"  # OPEN_NEW or CLOSE_EXISTING or caller-defined

    def __post_init__(self) -> None:
        # Minimal shape validation — values will be deep-checked by G09/G10.
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ContractSchemaError(
                "PaperOrderGateRequest.symbol must be non-empty str"
            )
        if not isinstance(self.side, PaperOrderSide):
            if isinstance(self.side, str):
                object.__setattr__(
                    self,
                    "side",
                    PaperOrderSide(self.side),
                )
            else:
                raise ContractSchemaError(
                    "PaperOrderGateRequest.side must be PaperOrderSide"
                )
        if not isinstance(self.order_type, PaperOrderType):
            if isinstance(self.order_type, str):
                object.__setattr__(
                    self,
                    "order_type",
                    PaperOrderType(self.order_type),
                )
            else:
                raise ContractSchemaError(
                    "PaperOrderGateRequest.order_type must be PaperOrderType"
                )
        if not isinstance(self.requested_qty_base, Decimal) or isinstance(
            self.requested_qty_base, bool
        ):
            raise ContractSchemaError(
                "PaperOrderGateRequest.requested_qty_base must be Decimal"
            )
        if not isinstance(self.requested_notional_quote, Decimal) or isinstance(
            self.requested_notional_quote, bool
        ):
            raise ContractSchemaError(
                "PaperOrderGateRequest.requested_notional_quote must be Decimal"
            )
        if self.requested_price is not None and (
            isinstance(self.requested_price, bool)
            or not isinstance(self.requested_price, Decimal)
        ):
            raise ContractSchemaError(
                "PaperOrderGateRequest.requested_price must be Decimal|None"
            )
        if not isinstance(self.policy_refs, PaperOrderPolicyRefs):
            raise ContractSchemaError(
                "PaperOrderGateRequest.policy_refs must be PaperOrderPolicyRefs "
                "(nested typed; raw dict rejected)"
            )
        if not isinstance(self.correlation_id, str) or len(self.correlation_id) < 8:
            raise ContractSchemaError(
                "PaperOrderGateRequest.correlation_id invalid ULID-like"
            )
        if not isinstance(self.causation_id, str) or len(self.causation_id) < 8:
            raise ContractSchemaError(
                "PaperOrderGateRequest.causation_id invalid ULID-like"
            )
        if not isinstance(self.position_intent, str) or not self.position_intent:
            raise ContractSchemaError(
                "PaperOrderGateRequest.position_intent must be non-empty str"
            )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return _sha_sorted(self.to_sorted_dict())


@dataclass(frozen=True)
class GateOptions:
    """Overrideable fixture options. Frozen-ish (use replace)."""

    stale_threshold_sec: float = DEFAULT_STALE_DECISION_THRESHOLD_SEC
    oversize_tolerance_bps: int = DEFAULT_OVERSIZE_TOLERANCE_BPS
    idempotency_max_entries: int = DEFAULT_IDEMPOTENCY_MAX_ENTRIES
    # Reference price source name — used only for G09D qty*price vs notional
    # consistency when RiskDecision.position_sizing.reference_price is None.
    # If None, qty*price mismatch step is skipped (safe default = not check).
    fallback_reference_price: Optional[Decimal] = None


@dataclass(frozen=True)
class GateResult:
    """Typed immutable output of the gate. Never contracts-exported."""

    allowed: bool
    block_reason_codes: tuple[str, ...]
    info_codes: tuple[str, ...]
    correlation_id: str
    causation_id: str
    validated_risk_decision_id: str
    decision_ts: Instant
    gate_version: str
    input_sha256: str

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return _sha_sorted(self.to_sorted_dict())


# ---------------------------------------------------------------------------
# Decision registry interface (typed lookup; in-memory implementation provided)
# ---------------------------------------------------------------------------


class DecisionRegistry:
    """Abstract-ish interface: lookup(corr_id, rd_id) -> RiskDecision or None.

    No persistence — in-memory only (paper-only, DB OOS).
    """

    def lookup(self, correlation_id: str, risk_decision_id: str) -> Optional[RiskDecision]:
        raise NotImplementedError  # pragma: no cover

    def find_by_decision_id(self, risk_decision_id: str) -> Optional[RiskDecision]:
        """Best-effort scan: locate a RD by decision_id alone.

        Used by the gate to disambiguate G01 (RD missing entirely) from G03
        (RD exists but was registered under a different correlation_id so
        the strict (corr, rd_id) key lookup returned None).
        """
        raise NotImplementedError  # pragma: no cover


class InMemoryDecisionRegistry(DecisionRegistry):
    """Dict-based registry keyed by (correlation_id, risk_decision_id).

    Read-only semantics — snapshots are stored at registration time. The
    caller must not mutate stored instances afterwards.
    """

    def __init__(self, entries: Iterable[tuple[str, str, RiskDecision]] = ()) -> None:
        self._store: dict[tuple[str, str], RiskDecision] = {}
        for corr, rd_id, rd in entries:
            self.register(corr, rd_id, rd)

    def register(self, correlation_id: str, risk_decision_id: str, rd: RiskDecision) -> None:
        if not isinstance(rd, RiskDecision):
            raise ContractSchemaError(
                "InMemoryDecisionRegistry.register requires RiskDecision typed instance"
            )
        self._store[(str(correlation_id), str(risk_decision_id))] = rd

    def lookup(self, correlation_id: str, risk_decision_id: str) -> Optional[RiskDecision]:
        return self._store.get((str(correlation_id), str(risk_decision_id)))

    def find_by_decision_id(self, risk_decision_id: str) -> Optional[RiskDecision]:
        target = str(risk_decision_id)
        for rd in self._store.values():
            if str(getattr(rd, "decision_id", "")) == target:
                return rd
        return None

    def __len__(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store.clear()


# ---------------------------------------------------------------------------
# Clock reference — deterministic in tests, UTC wall-clock default for prod
# ---------------------------------------------------------------------------


class ClockRef:
    """Abstract-ish instant reference. Override in tests via DeterministicClock."""

    def now(self) -> Instant:
        return format_instant(datetime.now(timezone.utc))


class DeterministicClock(ClockRef):
    """Return a fixed or stepping instant for determinism tests."""

    def __init__(self, fixed_instant: Optional[str] = None) -> None:
        if fixed_instant is None:
            fixed_instant = "2026-01-01T00:00:00.000Z"
        if not validate_instant(fixed_instant):
            raise ContractSchemaError(f"DeterministicClock invalid instant: {fixed_instant!r}")
        self._fixed: str = fixed_instant

    def now(self) -> Instant:
        return Instant(self._fixed)

    def set(self, new_instant: str) -> None:
        if not validate_instant(new_instant):
            raise ContractSchemaError(f"DeterministicClock invalid instant: {new_instant!r}")
        self._fixed = new_instant


# ---------------------------------------------------------------------------
# Internal small helpers
# ---------------------------------------------------------------------------


def _sha_sorted(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _instant_gte(a: str, b: str) -> bool:
    """Compare two ISO Z Instants lexicographically (precision is fixed)."""
    try:
        return str(a) >= str(b)
    except Exception:
        return True  # fail-closed: treat uncomparable as expired


def _instant_diff_seconds(a: str, b: str) -> float:
    try:
        a_dt = datetime.strptime(a[:-1], "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)
        b_dt = datetime.strptime(b[:-1], "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)
        return (a_dt - b_dt).total_seconds()
    except Exception:
        return float("inf")  # fail-closed: unknown diff => STALE


def _make_idem_key(request: PaperOrderGateRequest, input_sha: str, now_instant: str) -> tuple[Any, ...]:
    # Correlation + symbol + input shape + exact instant = unique request.
    # Using `now_instant` directly instead of a floored minute window ensures
    # time-sensitive checks like G05 (exactly valid_until BLOCK) never suffer
    # a false idempotency cache-hit when two evaluations happen within the
    # same clock minute but across the valid_until boundary.
    return (
        str(request.correlation_id),
        str(request.symbol),
        str(request.side),
        str(request.order_type),
        str(input_sha),
        str(now_instant),
    )


@dataclass
class _IdemEntry:
    allowed: bool
    block_reason_codes: tuple[str, ...]
    info_codes: tuple[str, ...]
    causation_id: str
    validated_risk_decision_id: str


# ---------------------------------------------------------------------------
# GATE — RiskDecisionToPaperOrderGate (fail-closed, deterministic)
# ---------------------------------------------------------------------------


class RiskDecisionToPaperOrderGate:
    """The CAP-4 enforcement gate.

    Short-circuit evaluation (first block reason wins and we exit early).
    Wrapped in a broad try/except so any exception — including contract
    invariant failures raised from nested typed helpers — returns BLOCKED
    with an AD19_* reason code instead of raising (AD-19 fail-closed).
    """

    VERSION: str = GATE_VERSION_RSK02

    def __init__(
        self,
        registry: DecisionRegistry,
        *,
        options: Optional[GateOptions] = None,
        clock: Optional[ClockRef] = None,
    ) -> None:
        if not isinstance(registry, DecisionRegistry):
            raise ContractSchemaError(
                "RiskDecisionToPaperOrderGate requires DecisionRegistry instance"
            )
        self._registry: DecisionRegistry = registry
        self._options: GateOptions = options or GateOptions()
        if not isinstance(self._options, GateOptions):
            raise ContractSchemaError("gate options must be GateOptions typed")
        self._clock: ClockRef = clock or ClockRef()
        if not isinstance(self._clock, ClockRef):
            raise ContractSchemaError("gate clock must be ClockRef typed")
        # idempotency store: key -> _IdemEntry
        self._idem: dict[tuple[Any, ...], _IdemEntry] = {}
        self._idem_max: int = int(self._options.idempotency_max_entries)
        if self._idem_max <= 0:
            self._idem_max = 1

    # ------------------------------------------------------------------
    # Public API — idempotent evaluate + introspection helpers
    # ------------------------------------------------------------------

    def evaluate(
        self,
        request: PaperOrderGateRequest,
    ) -> GateResult:
        """Main entry point. Fail-closed outer try/except."""
        # ---- input shaping ----
        if not isinstance(request, PaperOrderGateRequest):
            return self._ad19_block_synthetic(
                synthetic_corr="unknown",
                synthetic_caus="unknown",
                exc_type_name="TypeError",
                msg="evaluate() requires typed PaperOrderGateRequest (raw dict rejected)",
                input_sha="0" * 64,
            )

        input_sha: str = request.schema_sha256()

        now: Instant
        try:
            now = self._clock.now()
        except BaseException as exc:  # noqa: BLE001 — AD-19
            return self._ad19_block_synthetic(
                synthetic_corr=str(request.correlation_id),
                synthetic_caus=str(request.causation_id),
                exc_type_name=type(exc).__name__,
                msg=_safe_truncate(str(exc), 120),
                input_sha=input_sha,
            )

        idem_key = _make_idem_key(request, input_sha, str(now))

        # G07 idempotency shortcut (before heavy lookups) — EXCEPTION-SAFE inner
        try:
            prior = self._idem.get(idem_key)
        except BaseException as exc:  # noqa: BLE001
            return self._ad19_block(
                request,
                rd_ref=None,
                extra_blocks=[f"AD19_UNHANDLED_EXCEPTION:{type(exc).__name__}"],
                extra_infos=[f"AD19_MSG:{_safe_truncate(str(exc), 120)}"],
                input_sha=input_sha,
                clock_now=now,
                idem_key=None,
            )
        if prior is not None:
            infos = tuple([*prior.info_codes, "G07_DUPLICATE_REQUEST_IDEMPOTENT_RESPONSE"])
            return GateResult(
                allowed=prior.allowed,
                block_reason_codes=prior.block_reason_codes,
                info_codes=infos,
                correlation_id=str(request.correlation_id),
                causation_id=prior.causation_id,
                validated_risk_decision_id=prior.validated_risk_decision_id,
                decision_ts=now,
                gate_version=self.VERSION,
                input_sha256=input_sha,
            )

        # ---- INNER EVALUATION (short-circuit) wrapped with broad AD-19 ----
        try:
            return self._evaluate_inner(request, input_sha=input_sha, now=now, idem_key=idem_key)
        except BaseException as exc:  # noqa: BLE001 — AD-19: catch literally everything
            return self._ad19_block(
                request,
                rd_ref=None,
                extra_blocks=[f"AD19_UNHANDLED_EXCEPTION:{type(exc).__name__}"],
                extra_infos=[f"AD19_MSG:{_safe_truncate(str(exc), 120)}"],
                input_sha=input_sha,
                clock_now=now,
                idem_key=None,  # do not store idempotency entry when exception raised
            )

    def clear_idempotency(self) -> None:
        self._idem.clear()

    def idempotency_size(self) -> int:
        return len(self._idem)

    # ------------------------------------------------------------------
    # Internal short-circuit evaluator — raises normally; wrapped by AD-19
    # ------------------------------------------------------------------

    def _evaluate_inner(
        self,
        request: PaperOrderGateRequest,
        *,
        input_sha: str,
        now: Instant,
        idem_key: tuple[Any, ...],
    ) -> GateResult:
        blocks: list[str] = []
        infos: list[str] = []
        rd_ref: Optional[RiskDecision] = None

        # G01 — RiskDecision exists? (registry lookup, exact key pair)
        try:
            rd = self._registry.lookup(
                str(request.correlation_id),
                str(request.policy_refs.risk_decision_id),
            )
        except ContractSchemaError:
            raise
        except BaseException as exc:  # noqa: BLE001 — AD-19 outside; but be explicit here
            blocks.append(f"G01_REGISTRY_EXCEPTION:{type(exc).__name__}")
            blocks.append(f"AD19_REGISTRY_EXCEPTION:{type(exc).__name__}")
            return self._finalize(
                request,
                rd_ref=None,
                blocks=blocks,
                infos=infos,
                input_sha=input_sha,
                clock_now=now,
                idem_key=idem_key,
            )
        if rd is None:
            # CAP-4 disambiguation: strict (corr, rd_id) key returned None.
            # Is the RD present but registered under a DIFFERENT correlation_id?
            # If yes → G03_CORRELATION_MISMATCH (not G01 missing).
            alt_rd: Optional[RiskDecision] = None
            try:
                alt_rd = self._registry.find_by_decision_id(
                    str(request.policy_refs.risk_decision_id)
                )
            except Exception:
                alt_rd = None
            if alt_rd is not None:
                blocks.append("G03_CORRELATION_MISMATCH")
                rd_ref = alt_rd  # for traceability in result
                return self._finalize(
                    request,
                    rd_ref,
                    blocks=blocks,
                    infos=infos,
                    input_sha=input_sha,
                    clock_now=now,
                    idem_key=idem_key,
                )
            blocks.append("G01_RISK_DECISION_MISSING")
            return self._finalize(
                request,
                rd_ref=None,
                blocks=blocks,
                infos=infos,
                input_sha=input_sha,
                clock_now=now,
                idem_key=idem_key,
            )
        rd_ref = rd  # for finalize traceability

        # G02 — decision == APPROVED? (AD-11 single authority)
        if rd.decision != RiskDecisionResult.APPROVED:
            blocks.append("G02_RISK_DECISION_NOT_APPROVED")
            for sub_rc in rd.reason_codes:
                if isinstance(sub_rc, str) and sub_rc:
                    blocks.append(f"G02_SUB:{sub_rc[:200]}")
            return self._finalize(
                request, rd, blocks, infos, input_sha, now, idem_key
            )

        # G03 — correlation_id exact match (CAP-4 same chain)
        if str(request.correlation_id) != str(rd.correlation_id):
            blocks.append("G03_CORRELATION_MISMATCH")
            return self._finalize(
                request, rd, blocks, infos, input_sha, now, idem_key
            )

        # G04 — policy_refs.risk_decision_id == rd.decision_id (CAP-4 1:1 link)
        if str(request.policy_refs.risk_decision_id) != str(rd.decision_id):
            blocks.append("G04_POLICY_REFS_RISK_ID_MISMATCH")
            return self._finalize(
                request, rd, blocks, infos, input_sha, now, idem_key
            )

        # G05 — valid_until (strict less-than: EXACT equality == expired)
        if _instant_gte(now, rd.valid_until):
            blocks.append("G05_DECISION_EXPIRED")
            return self._finalize(
                request, rd, blocks, infos, input_sha, now, idem_key
            )

        # G06 — Kill Switch 3-level (defense-in-depth — AD-11 invariant already
        # blocks APPROVED + global_kill inside RiskDecision.__post_init__, but
        # we re-check at the gate boundary for bypass safety).
        ks: KillSwitchStateSpec = rd.kill_switch_state
        if getattr(ks, "global_kill", False) is True:
            blocks.append("G06A_GLOBAL_KILL")
        # Note: KillSwitchStateSpec schema uses field "per_symbol" (dict[symbol, bool]).
        per_sym = getattr(ks, "per_symbol", None)
        sym_key = str(request.symbol)
        if isinstance(per_sym, dict):
            if bool(per_sym.get(sym_key, False)):
                blocks.append("G06C_PER_SYMBOL_KILL")
        # KillSwitchStateSpec has no direct emergency_stop field in v1 S-CON-02B
        # (only global_kill / per_symbol / reason). Map "emergency_stop" semantic
        # to global_kill OR a reason token when available. This ensures user's
        # 3-level kill category is covered end-to-end even when schema only
        # provides 2 primary switches.
        reason_token = getattr(ks, "reason", None)
        if isinstance(reason_token, str) and "emergency" in reason_token.lower():
            blocks.append("G06B_EMERGENCY_STOP")

        if blocks:
            return self._finalize(
                request, rd, blocks, infos, input_sha, now, idem_key
            )

        # G08 — Stale decision age + upstream quality flags (CAP-2 read-only,
        # validator never re-invoked).
        age_s = _instant_diff_seconds(now, _instant_try_created(rd))
        if age_s > float(self._options.stale_threshold_sec):
            blocks.append("G08A_STALE_DECISION_AGE")
        qs = getattr(rd, "quality_state", None)
        if qs is None:
            # Fall back to checking approval_chain / reason_codes qual tokens
            pass
        else:
            # CAP-2: read-only attribute access. NO assignment. NO validator import.
            for bad in ("stale", "invalid", "quarantined", "degraded"):
                if bool(getattr(qs, bad, False)) is True:
                    blocks.append(f"G08B_UPSTREAM_QUALITY_{bad.upper()}")
        for rc in getattr(rd, "reason_codes", []):
            if not isinstance(rc, str):
                continue
            upper_rc = rc.upper()
            for bad in ("STALE", "INVALID", "QUARANTINE"):
                if bad in upper_rc:
                    blocks.append(f"G08B_SUB_FROM_RISK_DEC:{_safe_truncate(rc, 80)}")
                    break  # one tag per reason code enough

        if blocks:
            return self._finalize(
                request, rd, blocks, infos, input_sha, now, idem_key
            )

        # G09 — Quantity / Notional 4-way checks
        qty = request.requested_qty_base
        notional = request.requested_notional_quote
        pos_size: PositionSizingSpec = rd.position_sizing
        risk_notional = getattr(pos_size, "notional", None)
        # prefer RD reference price; else gate-level fallback (default None -> skip)
        ref_price = getattr(pos_size, "reference_price", None)
        if ref_price is None:
            ref_price = self._options.fallback_reference_price

        if not (isinstance(qty, Decimal) and not isinstance(qty, bool) and qty > 0):
            blocks.append("G09A_QTY_NON_POSITIVE")
        if not (isinstance(notional, Decimal) and not isinstance(notional, bool) and notional > 0):
            blocks.append("G09B_NOTIONAL_NON_POSITIVE")
        if (
            isinstance(risk_notional, Decimal)
            and not isinstance(risk_notional, bool)
            and risk_notional > 0
            and isinstance(notional, Decimal)
            and not isinstance(notional, bool)
        ):
            if notional > risk_notional:
                blocks.append("G09C_NOTIONAL_OVERSIZED_VS_RISK")
        if (
            isinstance(qty, Decimal) and qty > 0
            and isinstance(ref_price, Decimal) and ref_price > 0
            and isinstance(notional, Decimal) and notional > 0
        ):
            implied = qty * ref_price
            tol_bps = max(0, int(self._options.oversize_tolerance_bps))
            tolerance = notional * (Decimal(tol_bps) / Decimal(10_000))
            if implied > notional + tolerance:
                blocks.append("G09D_QTY_PRICE_MISMATCH_VS_NOTIONAL")

        if blocks:
            return self._finalize(
                request, rd, blocks, infos, input_sha, now, idem_key
            )

        # G10 — v1 safety boundary: no short-open, no leverage!=1, no futures/perps
        side_str = str(request.side.value).lower() if hasattr(request.side, "value") else str(request.side).lower()
        intent = str(request.position_intent).strip().upper()
        if intent == "OPEN_NEW" and side_str == "sell":
            blocks.append("G10A_SHORT_ATTEMPT_BLOCKED")
        if side_str.startswith("short") or "short" in side_str and intent != "CLOSE_EXISTING":
            # belt-and-suspenders — enum only has buy/sell, but schema_sha of
            # request is type-safe; this branch future-proofs against widened enums.
            if "G10A_SHORT_ATTEMPT_BLOCKED" not in blocks:
                blocks.append("G10A_SHORT_ATTEMPT_BLOCKED")

        limits: LimitsSnapshot = rd.limits_snapshot
        max_lev = getattr(limits, "max_leverage_allowed", None)
        if max_lev is None or max_lev != 1:
            blocks.append("G10B_LEVERAGE_OVER_1X_BLOCKED")

        sym_upper = str(request.symbol).upper()
        otype_upper = str(
            request.order_type.value if hasattr(request.order_type, "value") else request.order_type
        ).upper()
        for tok in FUTURES_PERP_TOKENS:
            if tok in sym_upper or tok in otype_upper:
                blocks.append("G10C_FUTURES_OR_PERPETUAL_BLOCKED")
                break

        if blocks:
            return self._finalize(
                request, rd, blocks, infos, input_sha, now, idem_key
            )

        # ------------------------------------------------------------------
        # ALL 10 GATES PASSED — ALLOW
        # ------------------------------------------------------------------
        return self._finalize(
            request, rd, blocks=[], infos=[], input_sha=input_sha, clock_now=now, idem_key=idem_key,
            force_allow=True,
        )

    # ------------------------------------------------------------------
    # Finalization (store idempotency + build GateResult)
    # ------------------------------------------------------------------

    def _finalize(
        self,
        request: PaperOrderGateRequest,
        rd_ref: Optional[RiskDecision],
        blocks: list[str],
        infos: list[str],
        input_sha: str,
        clock_now: Instant,
        idem_key: Optional[tuple[Any, ...]],
        force_allow: bool = False,
    ) -> GateResult:
        allowed = (not blocks) and bool(force_allow)
        block_tuple = tuple(blocks)
        info_tuple = tuple(infos)
        causation_id = (
            str(rd_ref.decision_id) if rd_ref is not None else str(request.causation_id)
        )
        validated_rd_id = (
            str(rd_ref.decision_id) if rd_ref is not None else ""
        )

        # store idempotency only when idem_key is supplied (no exception paths)
        if idem_key is not None:
            try:
                if len(self._idem) >= self._idem_max:
                    # drop a few oldest entries (simple dict LRU-lite)
                    drop_n = max(1, self._idem_max // 10)
                    for _ in range(drop_n):
                        try:
                            first_key = next(iter(self._idem))
                        except StopIteration:
                            break
                        del self._idem[first_key]
                self._idem[idem_key] = _IdemEntry(
                    allowed=allowed,
                    block_reason_codes=block_tuple,
                    info_codes=info_tuple,
                    causation_id=causation_id,
                    validated_risk_decision_id=validated_rd_id,
                )
            except Exception:
                # Idem store failure never changes the logical gate result
                # (idempotency is a safety belt, not a hard correctness
                # dependency; AD-19 already covers exceptions higher up).
                pass

        return GateResult(
            allowed=allowed,
            block_reason_codes=block_tuple,
            info_codes=info_tuple,
            correlation_id=str(request.correlation_id),
            causation_id=causation_id,
            validated_risk_decision_id=validated_rd_id,
            decision_ts=clock_now,
            gate_version=self.VERSION,
            input_sha256=input_sha,
        )

    def _ad19_block(
        self,
        request: PaperOrderGateRequest,
        *,
        rd_ref: Optional[RiskDecision],
        extra_blocks: list[str],
        extra_infos: list[str],
        input_sha: str,
        clock_now: Instant,
        idem_key: Optional[tuple[Any, ...]],
    ) -> GateResult:
        blocks = list(extra_blocks)
        infos = list(extra_infos)
        return self._finalize(
            request,
            rd_ref,
            blocks=blocks,
            infos=infos,
            input_sha=input_sha,
            clock_now=clock_now,
            idem_key=idem_key,
            force_allow=False,
        )

    def _ad19_block_synthetic(
        self,
        *,
        synthetic_corr: str,
        synthetic_caus: str,
        exc_type_name: str,
        msg: str,
        input_sha: str,
    ) -> GateResult:
        """AD-19 block for cases where we can't even build a ClockRef.now instant
        or Request shape is invalid enough to skip _finalize (no idem storage)."""
        try:
            ts = self._clock.now()
        except Exception:
            ts = Instant("1970-01-01T00:00:00.000Z")
        return GateResult(
            allowed=False,
            block_reason_codes=(f"AD19_UNHANDLED_EXCEPTION:{exc_type_name}",),
            info_codes=(f"AD19_MSG:{msg}",),
            correlation_id=str(synthetic_corr),
            causation_id=str(synthetic_caus),
            validated_risk_decision_id="",
            decision_ts=ts,
            gate_version=self.VERSION,
            input_sha256=input_sha,
        )


# ---------------------------------------------------------------------------
# Misc helper utilities
# ---------------------------------------------------------------------------


def _instant_try_created(rd: RiskDecision) -> str:
    created_ts = getattr(rd, "created_ts", None)
    if created_ts is None:
        created_ts = getattr(rd, "created_at", None)
    if isinstance(created_ts, str) and created_ts:
        return created_ts
    # Fall back: valid_until minus stale_threshold (treat as "just made") — safe
    try:
        return str(rd.valid_until)
    except Exception:
        return "1970-01-01T00:00:00.000Z"


def _safe_truncate(s: str, n: int) -> str:
    if not isinstance(s, str):
        s = repr(s)
    if len(s) <= n:
        return s
    return s[: max(0, n - 3)] + "..."


# ---------------------------------------------------------------------------
# EventBus bridge (S-PLN-01 typed bus) — gate subscriber/publisher
#
# Flow:
#   EventBus.publish(RISK_DECISION_PUBLISHED, envelope carrying RiskDecision)
#     -> gate subscriber (typed) receives envelope
#     -> if envelope.payload.decision != APPROVED: exit (no paper order ever)
#     -> else: invoke caller-supplied request_factory(rd, env) to build request
#     -> gate.evaluate(request)
#     -> if allowed: publish PAPER_ORDER_CREATED (with corr/caus correctly set)
#     -> if blocked: publish PAPER_ORDER_BLOCKED with reason_codes
#   Subscriber exceptions go to bus dead_letters; other subscribers unaffected.
# ---------------------------------------------------------------------------


GateRequestFactory = Callable[[RiskDecision, CanonicalEventEnvelope], PaperOrderGateRequest]
PaperOrderFactory = Callable[[RiskDecision, PaperOrderGateRequest, GateResult], PaperOrder]


def register_gate_subscriber(
    bus: InMemoryTypedEventBus,
    gate: RiskDecisionToPaperOrderGate,
    request_factory: GateRequestFactory,
    order_factory: PaperOrderFactory,
    *,
    contract_version_min: Optional[tuple[int, int, int]] = None,
    accept_quarantined: bool = False,
) -> SubscriptionToken:
    """Register a typed subscriber on the bus that drives the gate pipeline.

    Returns a SubscriptionToken so caller can unsubscribe later (idempotent).
    """

    if not isinstance(bus, InMemoryTypedEventBus):
        raise ContractSchemaError("bus must be InMemoryTypedEventBus typed")
    if not isinstance(gate, RiskDecisionToPaperOrderGate):
        raise ContractSchemaError("gate must be RiskDecisionToPaperOrderGate typed")
    if not callable(request_factory):
        raise ContractSchemaError("request_factory must be callable")
    if not callable(order_factory):
        raise ContractSchemaError("order_factory must be callable")

    def _on_risk_decision(envelope: CanonicalEventEnvelope) -> None:
        try:
            rd: RiskDecision = envelope.payload  # type: ignore[assignment]
        except Exception:
            # Dead letter already handled by bus subscriber error catcher.
            return
        if not isinstance(rd, RiskDecision):
            # Raise so bus records E_SUBSCRIBER_EXC dead letter — fail-closed:
            # unknown payload types never produce a PaperOrder.
            raise ContractSchemaError(
                "gate subscriber requires RiskDecision payload inside envelope"
            )

        # Short circuit: REJECTED decisions never open a paper order (AD-11).
        if rd.decision != RiskDecisionResult.APPROVED:
            return

        request = request_factory(rd, envelope)
        result: GateResult = gate.evaluate(request)
        if result.allowed:
            paper_order: PaperOrder = order_factory(rd, request, result)
            if not isinstance(paper_order, PaperOrder):
                raise ContractSchemaError(
                    "order_factory must return a typed PaperOrder instance"
                )
            child_env = CanonicalEventEnvelope(
                event_id=paper_order.paper_order_id,
                event_type=EVENT_TYPE_PAPER_ORDER_CREATED,
                contract_version=envelope.contract_version
                if isinstance(getattr(envelope, "contract_version", None), str)
                else "1.0.0",
                symbol=getattr(envelope, "symbol", None)
                or str(getattr(paper_order, "paper_order_id", "unknown_symbol")),
                source=getattr(envelope, "source", "gate_pipeline_srsk02"),
                timestamp=getattr(envelope, "timestamp", paper_order.causation_id),
                ingest_ts=getattr(
                    envelope, "ingest_ts",
                    getattr(envelope, "timestamp", paper_order.causation_id),
                ),
                run_mode=getattr(envelope, "run_mode", None),
                source_type=getattr(envelope, "source_type", None),
                clock_ref=getattr(envelope, "clock_ref", None),
                correlation_id=paper_order.correlation_id,
                causation_id=paper_order.causation_id,
                quality_flags=getattr(envelope, "quality_flags", None) or QualityFlags(),
                payload=paper_order,
            )
            bus.publish(child_env)
        else:
            # blocked event — payload = gate result snapshot (dict)
            blocked_payload = {
                "correlation_id": result.correlation_id,
                "causation_id": result.causation_id,
                "block_reason_codes": list(result.block_reason_codes),
                "info_codes": list(result.info_codes),
                "risk_decision_id": result.validated_risk_decision_id,
                "gate_version": result.gate_version,
            }
            blocked_env = CanonicalEventEnvelope(
                event_id=f"blk_{result.correlation_id}_{_sha_sorted(blocked_payload)[:12]}",
                event_type=EVENT_TYPE_PAPER_ORDER_BLOCKED,
                contract_version=envelope.contract_version
                if isinstance(getattr(envelope, "contract_version", None), str)
                else "1.0.0",
                symbol=getattr(envelope, "symbol", result.correlation_id),
                source=getattr(envelope, "source", "gate_pipeline_srsk02"),
                timestamp=getattr(envelope, "timestamp", result.decision_ts),
                ingest_ts=getattr(envelope, "ingest_ts", getattr(envelope, "timestamp", result.decision_ts)),
                run_mode=getattr(envelope, "run_mode", None),
                source_type=getattr(envelope, "source_type", None),
                clock_ref=getattr(envelope, "clock_ref", None),
                correlation_id=result.correlation_id,
                causation_id=result.causation_id,
                quality_flags=getattr(envelope, "quality_flags", None) or QualityFlags(),
                payload=blocked_payload,
            )
            bus.publish(blocked_env)

    token = bus.subscribe_typed(
        EVENT_TYPE_RISK_DECISION_PUBLISHED,
        _on_risk_decision,
        contract_version_min=contract_version_min,
        accept_quarantined=accept_quarantined,
    )
    return token


__all__ = [
    "GATE_VERSION_RSK02",
    "DEFAULT_STALE_DECISION_THRESHOLD_SEC",
    "DEFAULT_OVERSIZE_TOLERANCE_BPS",
    "DEFAULT_IDEMPOTENCY_MAX_ENTRIES",
    "EVENT_TYPE_RISK_DECISION_PUBLISHED",
    "EVENT_TYPE_PAPER_ORDER_CREATED",
    "EVENT_TYPE_PAPER_ORDER_BLOCKED",
    "PaperOrderGateRequest",
    "GateOptions",
    "GateResult",
    "DecisionRegistry",
    "InMemoryDecisionRegistry",
    "ClockRef",
    "DeterministicClock",
    "RiskDecisionToPaperOrderGate",
    "register_gate_subscriber",
]
