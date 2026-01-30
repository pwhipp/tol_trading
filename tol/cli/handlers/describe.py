import sys

from tol.load import load_tol_text
from tol.llm.client import ChatGptClient


def handle_describe(args) -> None:
    tol_text = sys.stdin.read()
    if not tol_text.strip():
        print("ERROR: No TOL document provided on stdin.", file=sys.stderr)
        sys.exit(1)

    try:
        tol_doc = load_tol_text(tol_text)
    except ValueError as exc:
        print(f"ERROR: Failed to parse TOL document: {exc}", file=sys.stderr)
        sys.exit(1)

    client = ChatGptClient.from_config(model_override=args.llm_model)

    try:
        response = client.describe_tol(tol_doc)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    for warning in response.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    print(response.content)
