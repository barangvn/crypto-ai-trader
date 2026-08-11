---
title: "PRD: Crypto AI Trader"
status: final
created: 2026-08-04
updated: 2026-08-04
product: crypto-ai-trader
source_brief: "../briefs/brief-crypto-ai-trader-2026-08-04/brief.md"
---

# PRD: Crypto AI Trader

## 1. Purpose and Product Boundary

Crypto AI Trader is a spot-market research, analytics, backtesting, and paper-trading system. It turns normalized market data into explainable opportunities, strategy evaluations, and risk-controlled simulated decisions. It is not a profit-guaranteeing product or investment-advice service.

**Hard v1 boundary:** spot only; no futures, leverage, shorting, real money, real orders, exchange API keys, private-account connectivity, or trading permissions. Any future live spot trading is a separate phase with independent product, security, legal/compliance, and approval gates.

The system must treat an AI score or strategy signal as a candidate only. A candidate becomes a paper order only after validation, independent risk approval, position sizing, and simulation rules pass.

## 2. Users and Roles

### Primary Persona: Developer / Operator

The initial user configures the project, runs analyses and simulated workflows, reviews data health, approves model promotions, and operates emergency controls. The user needs reproducible results, clear explanations, safe defaults, and a complete audit trail.

### Future Personas (out of MVP)

- **Operator:** manages system health, data adapters, risk controls, and incidents.
- **Trader / Researcher:** investigates opportunities, strategies, and reports without authority to bypass risk controls.
- **Admin:** manages access, policy, retention, and future secrets/permissions.

Role-based access control is a future requirement; MVP is single-operator but must not embed a design that assumes unrestricted multi-user trading authority.

## 3. Product Outcomes and Counter-metrics

### Desired outcomes

- An operator can explain why a paper-trading opportunity appeared, what data supported it, which regime applies, and why it was accepted or rejected.
- Research results remain reproducible across data, feature, strategy, model, and configuration versions.
- Model and strategy changes are promoted only through measurable validation and a human approval gate.
- Risk controls prevent unsafe simulated execution when data or system health is uncertain.

### Counter-metrics

- High apparent return that disappears after fees, slippage, latency, drawdown, or out-of-sample testing is failure, not success.
- More opportunities, trades, or model updates are not success if risk rejections, data-quality incidents, or instability increase.
- Low latency is not success when it weakens data integrity, observability, or fail-safe behavior.

## 4. User Journey: Safe Opportunity to Paper Result

1. The system receives or replays normalized public spot-market data.
2. The market scanner ranks eligible pairs and emits opportunity candidates.
3. The system assigns regime, feature values, strategy rationale, opportunity score, and confidence.
4. Validation rejects stale, incomplete, illiquid, too-wide-spread, or incompatible candidates.
5. The independent risk engine applies portfolio and per-position limits.
6. The position-sizing step proposes a size within approved limits.
7. The execution decision produces **only a simulated order** in v1.
8. The paper engine models fill, fee, slippage, latency, spread, and partial-fill effects.
9. Result, P&L, risk impact, and the decision trail become visible in the dashboard and audit log.

## 5. Functional Requirements

### 5.1 Market Data and Exchange Adapters

- **FR-001** The system shall define an exchange-independent adapter contract for public ticker, OHLCV, public trades, best bid/ask, order-book updates, market metadata, historical/replay data, and adapter health.
- **FR-002** The system shall keep exchange-specific connection, symbol, rate-limit, and schema behavior behind the adapter boundary.
- **FR-003** The system shall support replay/historical data as a first-class source; v1 shall not require live exchange connectivity.
- **FR-004** Every normalized market event shall include source, instrument, exchange timestamp, receive timestamp, event type, and data-quality status.
- **FR-005** The system shall identify and surface stale data, duplicate events, ordering/sequence gaps, disconnects, resynchronization events, and malformed payloads.
- **FR-006** The system shall not create new paper orders from a pair whose required data is stale, incomplete, or marked unhealthy.
- **FR-007** The system shall retain provenance linking each feature, signal, backtest result, and paper decision to its input data version/range.

### 5.2 Market Scanner and Feature Layer

- **FR-008** The scanner shall evaluate a configurable universe of spot pairs without assuming a particular exchange.
- **FR-009** For every eligible pair, the scanner shall calculate or ingest liquidity, volume, volatility, spread, momentum, trend, order-book imbalance, and opportunity-score inputs.
- **FR-010** The scanner shall support filtering pairs by configured data health, minimum liquidity, volume, spread, volatility, and market eligibility rules.
- **FR-011** The system shall calculate OHLCV-derived technical indicators using versioned configurations and disclose their inputs in the decision record.
- **FR-012** The system shall track BTC reference effects and market correlations as contextual/risk inputs, not as proof of causation.
- **FR-013** The system shall record why a pair was excluded, ranked, or selected.

### 5.3 Market Regime Detection and Strategy Compatibility

- **FR-014** The system shall assign one or more scored regime states: Bull, Bear, Sideways/Range, High Volatility, Low Volatility, and Transition/Uncertain.
- **FR-015** Each regime result shall carry confidence and a data/feature version.
- **FR-016** Transition/Uncertain shall be a first-class safety state; it shall reduce strategy confidence and may block strategies that require stable regimes.
- **FR-017** The strategy registry shall declare which regimes each strategy supports, is cautious in, or rejects.
- **FR-018** Risk policy shall support regime-sensitive limits. High Volatility and Transition/Uncertain shall never automatically increase exposure; any stricter or looser limits must be versioned and approved.

**Initial compatibility policy:** Trend Following and Momentum are MVP candidates because they are explainable, have well-understood measurable signals, and complement directional regimes. In Bull/Bear they may be eligible subject to spot-only long constraints; in Sideways they are de-prioritized. Mean Reversion is a future candidate for Range/Low Volatility once fill and risk assumptions are validated. Breakout, Volume Spike, Order Book Imbalance, Volatility Based, and AI/Adaptive strategies are extensibility targets, not MVP commitments.

### 5.4 Opportunity and Confidence Scoring

- **FR-019** An opportunity record shall include pair, timestamp, direction/long-only thesis, source strategy, regime, confidence, expected-return estimate, risk estimate, volatility, liquidity, spread, estimated fees, estimated slippage, and regime-compatibility score.
- **FR-020** The opportunity score shall be a decomposable score, not an opaque AI-only value; its component values and configured weights shall be visible to the operator.
- **FR-021** The system shall treat expected return as an estimate with uncertainty, not a promise.
- **FR-022** A candidate shall require all of: valid data, strategy eligibility, acceptable regime compatibility, sufficient confidence, positive estimated net-of-cost expectation, and Risk Engine approval before simulation.
- **FR-023** AI confidence alone shall never authorize an order simulation or override a validation or risk rejection.
- **FR-024** The system shall label low-confidence, high-cost, or data-degraded opportunities as non-actionable and retain the rejection reason.

### 5.5 Strategy Engine

- **FR-025** The architecture shall support pluggable Trend Following, Momentum, Breakout, Mean Reversion, Volume Spike, and Order Book Imbalance strategies without changing the scanner, risk engine, or paper engine contracts.
- **FR-026** Each strategy shall declare required inputs, eligible regimes, entry/exit/invalidation criteria, configuration version, and produced rationale.
- **FR-027** MVP shall activate no more than two strategies: Trend Following and Momentum, pending the open decision on their exact rules and validation thresholds.
- **FR-028** The system shall record strategy-specific performance and performance by regime; it shall not aggregate away poor regime-specific behavior.
- **FR-029** Strategy weighting may use approved regime compatibility and evaluation results, but shall not be changed by an unvalidated live-learning process.

### 5.6 AI Engine and Controlled Adaptive Learning

- **FR-030** AI capabilities may perform market classification, regime detection, opportunity scoring, probability estimation, feature importance, and strategy selection/weighting.
- **FR-031** AI outputs shall be versioned, reproducible, attributable to a model/feature/data version, and accompanied by confidence/uncertainty where applicable.
- **FR-032** AI shall not submit orders, bypass risk rules, alter position sizes, or change its own live/champion model without the governed lifecycle below.
- **FR-033** Every candidate model shall progress through: **Data → Train → Backtest → Out-of-Sample → Walk-Forward → Paper Trading → Evaluation → Challenger → Approval Gate → Champion → Live**.
- **FR-034** In v1, the lifecycle shall stop at Paper Trading, Evaluation, Challenger, and Approval Gate; any “Live” target remains disabled and out of scope.
- **FR-035** A candidate failing any required stage or minimum sample threshold shall be rejected and retained with its rejection evidence.

### 5.7 Champion / Challenger and Model Registry

- **FR-036** The registry shall record model/strategy identifier, version, training data period, feature set, parameters, evaluation windows, metrics, approval status, and rollback predecessor.
- **FR-037** A Challenger shall run in isolated backtest/paper evaluation and shall not automatically replace the Champion.
- **FR-038** Promotion shall require a documented approval gate and comparison across net return, maximum drawdown, Sharpe, Sortino, profit factor, stability, trade count, fees, slippage, and regime-specific performance.
- **FR-039** Promotion shall be rejected when high return is accompanied by unacceptable drawdown, insufficient trades, unstable regime performance, degraded cost assumptions, or weaker out-of-sample/walk-forward results.
- **FR-040** The system shall support rollback to the prior Champion or to a safe disabled/observe-only state when defined degradation thresholds are breached.
- **FR-041** A model/strategy change shall be auditable with the approver, rationale, evidence, timestamp, and prior state.

### 5.8 Overfitting Protection and Backtesting

- **FR-042** Training, validation, test, and out-of-sample data partitions shall be time-ordered and mutually controlled to prevent leakage.
- **FR-043** The evaluation process shall check and document feature leakage, look-ahead bias, survivorship/delisting bias, split contamination, and target leakage risks.
- **FR-044** Walk-forward validation shall use versioned rolling/expanding windows and record window definitions with results.
- **FR-045** Backtests shall model configured fees, slippage, latency assumptions, position sizing, stop loss, take profit, regime context, multiple strategies, and portfolio-level risk.
- **FR-046** A backtest result shall disclose its data range, data source, universe, assumptions, strategy/model versions, and limitations.

### 5.9 Paper Trading and Trading Pipeline

- **FR-047** Paper trading shall use real-time or replay market data without sending an exchange order.
- **FR-048** The paper engine shall model configurable fees, slippage, latency, spread, partial fills, and execution assumptions; all assumptions shall be reported with results.
- **FR-049** The system shall execute the logical pipeline: **Signal → Validation → Risk Check → Position Sizing → Execution Decision → Order Simulation → Result**.
- **FR-050** The Validation and Risk Check stages shall independently reject a signal; rejection shall terminate the pipeline and record the reason.
- **FR-051** A simulated position shall maintain entry/exit basis, size, stop/take-profit policy, cost model, realized/unrealized P&L, risk state, and source decision identifiers.

### 5.10 Risk Engine and Safety Controls

- **FR-052** The Risk Engine shall be strategy- and model-independent and shall have authority to reject a candidate.
- **FR-053** Risk policy shall support position sizing, maximum position size, maximum portfolio exposure, maximum open positions, maximum daily loss, maximum drawdown, maximum consecutive losses, stop loss, take profit, correlation/exposure limits, fee/slippage controls, and long-only spot constraints.
- **FR-054** Emergency stop and kill switch shall halt new paper order simulations immediately and surface the reason/state to the operator.
- **FR-055** Market-data or adapter/API failure shall trigger a safe mode that blocks new simulations for affected scope; recovery shall require validated health.
- **FR-056** Risk policy values, overrides, exceptions, and rejection decisions shall be versioned and audit logged.

### 5.11 Dashboard, Observability, and Reporting

- **FR-057** The dashboard shall show system/adaptor status, market status, active opportunities, AI confidence, regime, active strategies, paper positions, P&L, drawdown, model/Champion/Challenger state, learning/evaluation history, risk state, logs, and emergency-stop state.
- **FR-058** The dashboard shall allow an operator to inspect the decision trail for every opportunity, rejected candidate, simulated order, model promotion, and rollback.
- **FR-059** Performance reporting shall include P&L, total/net return, win and loss rate, average win/loss, profit factor, maximum drawdown, Sharpe, Sortino, fees, slippage, latency, trade count, strategy performance, model performance, and regime performance.
- **FR-060** The system shall distinguish gross and net metrics and shall never present performance without the applicable costs and risk context.

### 5.12 Security and Future Trading Gates

- **FR-061** No API key, secret, or trading credential shall be created, stored, requested, or used in v1.
- **FR-062** Future credential handling shall use secrets management, API-key isolation, minimum permissions, access control, audit logging, and explicit trading-permission gates.
- **FR-063** Future real-trading activation shall require a separate approved phase, threat model, legal/compliance review, tested kill switch, and explicit human authorization; it is not enabled by this PRD.

## 6. Acceptance Criteria

- **AC-01 Market data:** Given a replayed or public-data event, the system records normalized fields and provenance; when data is stale, malformed, or sequence-gapped, the affected pair is visibly unhealthy and cannot create a new simulated order.
- **AC-02 Scanner:** Given an eligible universe, the scanner records liquidity, volume, volatility, spread, momentum, trend, order-book imbalance, score inputs, and an inclusion/exclusion reason for each evaluated pair.
- **AC-03 Regime:** Given feature input, the system returns at least the six required regime states with confidence; Transition/Uncertain reduces eligibility according to policy.
- **AC-04 Scoring:** An opportunity detail contains every FR-019 component; removing Risk Engine approval prevents simulation even if AI confidence is high.
- **AC-05 Strategies:** MVP can evaluate Trend Following and Momentum independently, records their regime compatibility, and does not claim unavailable strategies are implemented.
- **AC-06 AI governance:** A candidate model missing an out-of-sample, walk-forward, or paper evaluation result cannot become Champion.
- **AC-07 Champion/Challenger:** A Challenger produces a comparison including all FR-038 metrics; it cannot replace the Champion without an approval record.
- **AC-08 Overfitting:** Evaluation artifacts identify the time partitions and verify the configured leakage/look-ahead checks before a result is considered promotable.
- **AC-09 Paper trading:** A paper result records cost and fill assumptions, including fees, slippage, latency, spread, and partial-fill behavior.
- **AC-10 Risk:** A configured max-loss, max-drawdown, data-failure, or kill-switch condition rejects or halts new paper simulations and records the reason.
- **AC-11 Reporting:** Performance reports include net-of-cost and risk metrics plus strategy/model/regime breakouts.
- **AC-12 Safety:** No component in the delivered MVP can create a real order, use a real API key, or enable futures, leverage, or shorting.

## 7. Non-functional Requirements

- **NFR-001 Latency:** The system shall measure ingest-to-decision and simulation latencies. Numeric SLOs remain an open decision and must be established per provider, universe, and deployment target before implementation acceptance.
- **NFR-002 Reliability:** Adapter disconnects, rate limits, malformed messages, and data gaps shall be detectable, logged, and fail closed for the affected scope.
- **NFR-003 Scalability:** The scanner shall support expansion of the configured pair universe without changing public contracts; capacity targets are deferred until the MVP universe is selected.
- **NFR-004 Observability:** Structured logs, health metrics, decision traces, alerts, data-quality indicators, risk events, and model-drift signals shall be available for investigation.
- **NFR-005 Fault tolerance:** A failure in one adapter/pair shall be isolated where possible and shall not silently corrupt unrelated decisions.
- **NFR-006 Data integrity:** Immutable/raw event provenance, timestamp semantics, sequence-gap handling, and versioned transformations shall permit reconstruction of a reported decision.
- **NFR-007 Reproducibility:** Backtest, evaluation, and model-promotion records shall be reproducible from versioned inputs, configurations, and assumptions.
- **NFR-008 Security:** v1 shall operate without secrets or trading credentials; future privileged paths must default deny and remain separately gated.

## 8. MVP Scope

**Included:** replay/historical data through an adapter contract; limited pair universe; data health; OHLCV, volume, volatility, and selected indicators; regime scoring; Trend Following and Momentum candidates; explainable opportunity/confidence scoring; fee/slippage-aware backtest; out-of-sample and initial walk-forward evaluation; paper portfolio; independent risk checks; basic registry/challenger evidence; rollback/kill-switch design and testable paper controls; operator dashboard/reporting.

**Deferred:** live exchange connection requiring keys, real orders, real funds, all additional strategy families, futures/leverage/shorts, multi-exchange execution, autonomous promotion, broad multi-user access, mobile app, and any return promise.

## 9. Open Questions / Decisions Needed

1. Which first exchange/replay provider, data license, symbol normalization rules, and source-health contract will be used?
2. What is the initial pair universe, quote currency, timeframes, order-book depth, and historical lookback?
3. What numeric low-latency, availability, recovery, and acceptable-data-loss objectives apply to the MVP?
4. What precise Trend Following and Momentum rules, parameters, regime eligibility, and success/rejection thresholds are approved for MVP?
5. Which AI model family is appropriate for the first scope, and what explainability/calibration standard is required?
6. What score weights, confidence thresholds, net-of-cost expectation threshold, and risk defaults are approved?
7. What paper fill model, fee schedule, slippage curve, latency model, and partial-fill assumptions will be used?
8. What database/storage approach supports raw events, derived features, research artifacts, and retention within the selected deployment constraints?
9. Is the technology stack Python, Node.js, or hybrid; what are the operator/deployment constraints that decide it?
10. What minimum sample, metric thresholds, regime coverage, approver, and degradation thresholds govern promotion and rollback?
11. What target geography and product boundary apply; what legal/compliance review is needed before any customer-facing scoring, account connection, or live trading scope?
12. Who owns the emergency stop, kill switch, exception approval, and final live-trading authorization in a future phase?

## 10. Dependencies and Next Handoff

This PRD depends on the Product Brief and intentionally defers technical mechanism choices to architecture. The next architecture phase must define adapter boundaries, event/data contracts, storage, service topology, technology selection, observability design, threat model, and the safe separation between paper and future live paths. Epics and stories follow only after architecture and, if needed, UX requirements are sufficiently defined.
