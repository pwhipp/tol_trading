# Trading Orchestration Language (TOL)
## Version 1 — Normative Specification

## 1. Introduction

The Trading Orchestration Language (TOL) is a declarative language for
describing multistep trading operations in a deterministic, auditable,
and dependency-aware manner.

TOL specifies *what* trades should occur and *how they relate*.
It does not specify *why* trades are chosen.

This document defines the **normative semantics** of TOL.

---

## 2. Conformance Language

The keywords **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL**
in this document are to be interpreted as described in RFC 2119.

---

## 3. Design Goals

TOL is designed to be:

- Deterministic
- Dependency-driven
- Crash-safe
- Human-readable
- Minimal

TOL is intentionally not a trading strategy language.

---

## 4. Abstract Model

This section defines the abstract entities and invariants of TOL.
No execution semantics are defined here.

### 4.1 Document

A TOL document (D) is a mapping with the following fields:

```
    D = {
        version: ℕ,
        mode: {paper, live},
        actions: [a₁, a₂, …, aₙ]
    }
```

The order of `actions` is significant and MUST be preserved.

### 4.2 Actions

Each action (A) in D.actions is defined as a mapping with the following fields:

```
    A = {
        [action_type ∈ {sell, buy, target}]:
            {
                symbol: ∈ TICKERS,
                *parameters: defined by action type below
            }
        }
```

Each action executes at most once.

### 4.3 Derived Action Identifier

Each action has a derived identifier:

    id(a) = lower(type) ∘ upper(symbol)

This identifier is used for dependency resolution.

**Invariance rule:**

For any two distinct actions `aᵢ` and `aⱼ`:

    id(aᵢ) ≠ id(aⱼ)

Documents violating this invariant are invalid and MUST be rejected.

> **Rationale**
>
> Actions with identical type and symbol are always reducible.
> Requiring uniqueness eliminates ambiguity and ensures deterministic execution.

### 4.4 Instruments and Tickers

A **ticker** is a string identifier that names a tradable instrument
within the execution environment.

Let:

    TICKERS = the set of all ticker identifiers recognized by the
              execution environment.

The TOL specification does not define the contents of `TICKERS`.
Membership in `TICKERS` is determined at execution time by the
underlying broker or execution adapter.

### 4.5 Action Parameters

- **sell**

  parameters = {quantity}


- **buy**

  parameters = {quantity, using}

- **target**

  parameters = {percent, using}

### 4.5.1 Action Parameter Definitions

This section defines the parameters used by TOL actions.
Each parameter is defined independently of the actions that use it.

##### 4.5.1.1 quantity

A **quantity** specifies an amount to be bought or sold.

A quantity MUST be exactly one of the following:

- **Absolute quantity**  
  A positive integer representing a number of units (e.g. 100).

- **Percentage quantity**  
  A percentage value as defined in [Section 4.5.3.3](#4533-percent) (e.g. 50%).

- **Monetary quantity**  
  A currency-denominated monetary value (e.g. $100).

- `ALL`  
  A special value representing the entire available amount (e.g. ALL).

The interpretation of a quantity is context-dependent and depends on:
- the action type (BUY or SELL)
- the available sources at execution time#### 4.5.1 Quantity

##### 4.5.1.2 using

The **using** parameter specifies the funding sources available to a BUY
or TARGET action.

The value of `using` MUST be a non-empty set of sources.

Each source MUST be one of:
- `CASH` (e.g. CASH)
- one of TICKERS ([Section 4.4](#44-instruments-and-tickers)) (e.g. VOO)
- a derived identifier of a SELL action (e.g. sellTSLA)

If omitted, the default value of `using` is `[ CASH ]`.

The order of sources in `using` is not significant.

##### 4.5.3.3 percent

The **percent** parameter represents a fractional proportion of an available amount.

A percent value MUST:
- be syntactically expressed with a trailing `%` symbol
- represent a value strictly greater than `0%`
- represent a value less than or equal to `100%`

e.g. 50%

A percent actual quantity is resolved at execution time relative to the available value
of the relevant sources.

---

## 5. Semantics

### 5.1 Static Semantics

A TOL document is well-formed if and only if all the following hold:

1. `version` and `mode` are present and valid.
2. Each action contains exactly one action type.
3. `(type, symbol)` pairs are unique across all actions.
4. BUY and TARGET actions reference only valid sources.
5. Derived action identifiers may only reference SELL actions declared earlier in the same document.
6. TARGET actions MUST NOT reference other TARGET actions.
7. The implied dependency graph MUST be acyclic.

Documents that are not well-formed MUST be rejected prior to execution.

### 5.2 Dependency Semantics

Actions form a directed acyclic graph (DAG).

- SELL actions introduce no dependencies.
- BUY and TARGET actions depend on all referenced sources.
- Dependencies are resolved implicitly; no explicit dependency syntax exists.

Execution order is derived via topological sorting.
Where multiple actions are eligible, declaration order MUST be respected.

### 5.3 Dynamic Semantics

Dynamic semantics describe how TOL actions interact with the execution
environment at runtime.

Execution occurs relative to a **portfolio state**, which includes:
- available cash balances
- current holdings
- any other execution-environment–specific constraints

The TOL specification does not define the structure or contents of the
portfolio state beyond what is required to evaluate action feasibility.

At runtime:

- A SELL action is feasible only if the portfolio contains a sufficient
  holding of the specified instrument.
- A BUY action is feasible only if the portfolio provides sufficient
  value from the specified `using` sources.
- A TARGET action is feasible only if the required implicit BUY and/or
  SELL actions are feasible when evaluated.

Insufficient holdings, insufficient funds, or invalid instruments are
runtime errors and MUST be reported as execution failures.

### 5.4 Execution Semantics

Execution proceeds as follows:

1. The document is validated for well-formedness.
2. TARGET actions are expanded into implicit BUY and/or SELL actions.
3. Actions execute in dependency order.
4. An action executes only after:
   - all dependencies have completed successfully, and
   - the action is dynamically feasible ([Section 5.3](#53-dynamic-semantics)).
5. Each action executes at most once.

If an action fails:
- Execution MUST halt.
- Successfully completed actions MUST NOT be retried.
- The document is considered partially executed.

---

## 8. Error Conditions

A TOL interpreter MUST report errors clearly and deterministically, including:

- Invalid document structure
- Duplicate action identifiers
- Invalid or unresolved dependencies
- Insufficient funds or holdings
- Execution failures

---

## 9. Explicit Non-Goals

TOL does not define, and will not define:

- Trading strategies
- Conditional logic
- Time-based execution
- Market indicators
- Arithmetic expressions
- Risk management policies

These concerns MUST be handled outside the TOL document.

---

## 10. Versioning and Compatibility

Future versions of TOL MAY extend the language.
Backward-incompatible changes MUST increment the major version number.

## Appendix A JSON Schema

See [TOL_JSON_SCHEMA.json](TOL_JSON_SCHEMA.json).