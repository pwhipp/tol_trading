# Trading Orchestration Language (TOL)

<div style="text-align: right;">
  <a href="https://creativecommons.org/licenses/by-nc/4.0/">
    <img src="https://licensebuttons.net/l/by-nc/4.0/88x31.png"
         alt="License: CC BY-NC 4.0">
  </a>
</div>

## What is TOL?

TOL is a **declarative language for orchestrating trades**, not a strategy engine.

You describe *what* trades should occur and *how they depend on each other*.
The interpreter guarantees deterministic, dependency-safe execution.

---

## What TOL Is Good At

- Coordinating multi-leg trades
- Ensuring sells fund later buys
- Expressing portfolio targets
- Producing reviewable execution plans
- Preventing ambiguous or unsafe execution

---

## What TOL Is Not

TOL does **not**:

- Pick trades for you
- Predict prices
- Contain conditionals or indicators
- Execute time-based strategies
- Replace your trading logic

Those belong elsewhere.

---

## Core Concepts

### Actions

TOL supports three action types:

- **sell** — dispose of an existing holding
- **buy** — acquire a holding using defined funding sources
- **target** — express a desired portfolio allocation

Each action appears **once**, executes **once**, and is uniquely identified by
its type and symbol (e.g. `sellNVDA.NASDAQ`, `buyTSLA.NASDAQ`).

---

### Dependencies are implicit

You never write dependencies explicitly.

If a BUY references the proceeds of a SELL, the dependency is inferred.
Execution order is derived automatically and deterministically.

---

### Execution is deterministic

Given the same account state and market conditions, a valid TOL document
will always execute the same way.

No hidden logic. No surprises.

---

## Example

```yaml
version: 1

settings:
  mode: paper

actions:
  - sell:
      symbol: NVDA.NASDAQ
      quantity: ALL

  - buy:
      symbol: TSLA.NASDAQ
      quantity: 50%
      using: [sellNVDA.NASDAQ]

  - buy:
      symbol: VOO.NYSE
      quantity: 50%
      using: [sellNVDA.NASDAQ]
```

This expresses intent clearly:
- Sell NVDA on NASDAQ
- Split the proceeds evenly between TSLA and VOO on their respective exchanges

Cash sources are always explicit about currency (e.g. `CASH[USD]`), and cash
amounts include both a currency symbol and code (e.g. `$1,000 (USD)`).

Conversions between cash currencies are expressed with `convert` actions:

```yaml
version: 1

settings:
  mode: paper

actions:
  - convert:
      amount: $1,000 (USD)
      to: CASH[AUD]
```

When generating TOL from natural language, the configuration can supply
`default_exchange` and `default_currency` values to fill in missing exchange
or currency information before output.

## Why TOL?
Because complex trades deserve:

  * Clear intent
  * Explicit funding
  * Deterministic execution
  * Auditability

TOL gives you those guarantees — and nothing more.

## Where to go next

1. Use tol generate to create a tol document from natural language
2. Review the generated tol document (see [TOL_SPEC.md](TOL_SPEC.md) for full normative semantics)
3. Use tol check to validate execution documents
4. Use tol run to execute (paper or live)

TOL is a tool for traders who value clarity over cleverness.

## License

This project is licensed under the **Creative Commons Attribution–NonCommercial 4.0 International (CC BY-NC 4.0)** license.

You are free to use, modify, and adapt this work for non-commercial purposes, provided appropriate credit is given.

Commercial use is not permitted without explicit permission from the author.

See the LICENSE file for full details.
