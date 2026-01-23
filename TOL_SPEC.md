# Trading Orchestration Language (TOL) — Specification

This document defines the **formal semantics** of the Trading Orchestration Language (TOL).

TOL is a **declarative orchestration language** for executing multi-step trades safely and deterministically.
It specifies *what* trades should occur and *how they relate*, not *why* they were chosen.

This specification is **normative**.

---

## 1. Design goals

TOL is designed to be:

- **Human-readable**
- **Deterministic**
- **Crash-safe**
- **Dependency-driven**
- **Minimal**

TOL is intentionally **not** a trading strategy language.

---

## 2. Document structure

```yaml
version: 1

settings:
  mode: paper | live

actions:
  - <action_type>:
      ...
```

- `settings.mode` **must** be specified and explicitly selects `paper` or `live` trading.
- `actions` is an ordered list; declaration order is significant for resolution.

---

## 3. Actions and identifiers

An **action**:

- Is one entry in the `actions` list
- Has exactly one `action_type`
- Executes at most once

Actions form a **directed acyclic graph (DAG)**.

### 3.1 Derived action identifiers

Actions do **not** explicitly declare identifiers.

Instead, the interpreter derives a stable identifier for each action using the convention:

```
<actionType><TICKER>
```

Where:
- `<actionType>` is the action name in camelCase (`sell`, `buy`, `target`)
- `<TICKER>` is the instrument ticker in upper case

Examples:
- `sellNVDA`
- `buyTSLA`
- `targetVOO`

These derived identifiers:

- Are stable and deterministic
- Are used internally by the interpreter
- May be referenced in `using` clauses when needed

If multiple actions of the same type and ticker appear, the interpreter must disambiguate deterministically (e.g. by declaration order).

---

## 4. Supported action types (MVP)

- `sell`
- `buy`
- `target`

---

## 5. Quantity model (unified)

All BUY and SELL actions use a single quantity model.

A quantity may be expressed as:

| Form | Meaning |
|----|--------|
| Integer | Number of shares |
| Percentage | Percentage of available amount |
| Currency | Monetary value |
| `ALL` | Entire available amount (equivalent to 100%) |

**A quantity is always interpreted relative to the action type and its context.**

---

## 6. SELL action

### Purpose
Dispose of an existing holding.

### Schema
```yaml
sell:
  symbol: <TICKER>
  quantity: <quantity>
```

### Semantics
- SELL actions operate only on existing holdings
- SELL actions never depend on other actions
- All SELL actions may execute concurrently
- Each SELL action produces proceeds usable by later actions

---

## 7. BUY action

### Purpose
Acquire a holding.

### Schema
```yaml
buy:
  symbol: <TICKER>
  quantity: <quantity>
  using:
    - CASH
    - <derivedActionId>
    - <TICKER>
```

The `using` property is **optional**.

If omitted, the BUY action is funded **entirely from available CASH**.

### Semantics
- BUY actions depend on all referenced sources in `using`
- Quantity is interpreted relative to the total value of those sources
- BUY actions execute only once all dependencies are resolved
- If insufficient value exists to satisfy the quantity, the action fails
- BUY actions referencing the same sources are resolved in declaration order

---

## 8. TARGET action

### Purpose
Express a desired portfolio state.

### Schema
```yaml
target:
  symbol: <TICKER>
  percent: <percentage>
  using:
    - CASH
    - <TICKER>
```

The `using` property is **optional**.

If omitted, only CASH may be used to satisfy the target.

### Semantics
The interpreter must:

1. Compute current portfolio value
2. Compute the desired value for the target symbol
3. Determine the required delta
4. Generate implicit BUY and/or SELL actions
5. Execute them using normal dependency rules

TARGET actions:
- Must not depend on other TARGET actions
- Are resolved **in declaration order**
- Fail if the target cannot be satisfied using the specified sources

---

## 9. Dependency inference

Dependencies are inferred when:
- A BUY or TARGET references a derived action identifier
- A BUY or TARGET references an existing holding

SELL actions never introduce dependencies.

Execution order is derived automatically.

---

## 10. Execution guarantees

A compliant interpreter guarantees:

- Deterministic execution
- No repeated actions
- Crash-safe resumption
- Clear error reporting
- Reviewable execution plans

---

## 11. Explicit non-goals

TOL does **not** support:

- Conditionals
- Arithmetic expressions
- Indicators
- Strategy logic
- Iteration
- Time-based behaviour

These belong outside TOL.

---

## 12. Status

This specification defines the **MVP semantics** of TOL.

Implicit camelCase action identifiers, the unified quantity model,
declaration-order resolution, and deterministic execution
are **foundational and non-negotiable**.
