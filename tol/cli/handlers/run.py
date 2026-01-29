import sys


def handle_run(args) -> None:
    from tol.parser.dag import compute_execution_levels
    from tol.parser.planner import plan_actions
    from tol.load import load_tol_text

    mode = args.mode
    dry_run = args.dry_run
    tol_text = sys.stdin.read()

    print("TOL CLI — Proof of Concept")
    print("-" * 40)

    if not tol_text.strip():
        print("ERROR: No TOL document provided on stdin.", file=sys.stderr)
        sys.exit(1)

    print("TOL input       : stdin")
    print(f"Execution mode  : {mode}")

    if dry_run:
        print(f"Dry run level   : {dry_run}")
    else:
        print("Dry run         : NO (execution requested)")

    print()
    print("Planned behaviour:")
    print("-" * 20)

    if dry_run is None:
        if mode == "live":
            print("• This would EXECUTE trades against the LIVE IBKR account.")
            print("• Orders would be placed and persisted.")
        else:
            print("• This would EXECUTE trades against the PAPER IBKR account.")
            print("• Orders would be placed and persisted.")

    elif dry_run == "local":
        print("• Parse and validate the TOL document only.")
        print("• Build dependency graph.")
        print("• NO portfolio queries.")
        print("• NO price queries.")
        print("• NO broker connectivity.")

    elif dry_run == "portfolio":
        print("• Parse and validate the TOL document.")
        print("• Build dependency graph.")
        print("• Query portfolio holdings.")
        print("• Query market prices.")
        print("• Compute quantities and targets.")
        print("• Detect obvious errors (insufficient holdings, absurd quantities).")
        print("• NO orders will be placed.")

    elif dry_run == "broker":
        print("• Parse and validate the TOL document.")
        print("• Build dependency graph.")
        print("• Connect to IBKR gateway.")
        print("• Resolve contracts.")
        print("• Validate order parameters with broker.")
        print("• NO orders will be placed.")

    print()
    print("NOTE:")
    print("• This is a stub CLI.")
    print("• No actions have been executed.")
    print("• No state has been persisted.")
    print("• This interface is designed to be shared with a future GUI.")

    print("-" * 40)

    print()
    print("Derived execution plan:")
    print("-" * 20)

    tol_doc = load_tol_text(tol_text)
    actions = plan_actions(tol_doc)

    if dry_run == "portfolio":
        from tol.cli.handlers.portfolio_dry_run import run_portfolio_dry_run

        print()
        print("Portfolio dry run:")
        print("-" * 20)
        report_lines = run_portfolio_dry_run(actions, mode)
        for line in report_lines:
            print(line)
        print()
    elif dry_run == "broker":
        from tol.cli.handlers.broker_dry_run import run_broker_dry_run

        print()
        print("Broker dry run:")
        print("-" * 20)
        report_lines = run_broker_dry_run(actions, mode)
        for line in report_lines:
            print(line)
        print()

    for action in actions:
        print(f"• {action.derived_id}")
        print(f"    type        : {action.action_type}")
        print(f"    symbol      : {action.symbol}")
        if action.quantity is not None:
            print(f"    quantity    : {action.quantity}")
        if action.percent is not None:
            print(f"    percent     : {action.percent}")
        if action.using_classified:
            print("    using:")
            for source, kind in action.using_classified:
                print(f"      - {source:<10} ({kind})")
        if action.depends_on:
            print(f"    depends_on  : {action.depends_on}")

    levels = compute_execution_levels(actions)

    print()
    print("Execution plan:")
    print()

    for level_num, level in enumerate(levels, start=1):
        for action_id in level:
            prefix = f"{level_num}=" if len(level) > 1 else f"{level_num} "
            print(f"{prefix} {action_id}")

            action = next(a for a in actions if a.derived_id == action_id)
            if action.depends_on:
                print("     depends on:")
                for dep in action.depends_on:
                    print(f"        - {dep}")
        print()
