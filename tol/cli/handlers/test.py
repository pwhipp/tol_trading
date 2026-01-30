import sys

from tol.load import dump_tol, load_tol_text


def handle_test(args) -> None:
    tol_text = sys.stdin.read()
    if not tol_text.strip():
        print("ERROR: No TOL document provided on stdin.", file=sys.stderr)
        sys.exit(1)

    try:
        tol_doc = load_tol_text(tol_text)
    except ValueError as exc:
        print(f"ERROR: Failed to parse TOL document: {exc}", file=sys.stderr)
        sys.exit(1)

    output = dump_tol(tol_doc)
    print(output)
    if args.echo:
        print(output, file=sys.stderr)
