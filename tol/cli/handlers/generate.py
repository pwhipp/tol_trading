import sys

from tol.load import check_tol_syntax_and_static_semantics, dump_tol
from tol.llm.client import ChatGptClient


def handle_generate(args) -> None:
    prompt_text = sys.stdin.read()
    if not prompt_text.strip():
        print("ERROR: No natural language request provided on stdin.", file=sys.stderr)
        sys.exit(1)

    client = ChatGptClient.from_config(model_override=args.llm_model)

    try:
        response = client.generate_tol(prompt_text, mode_override=args.mode)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    for warning in response.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    check_tol_syntax_and_static_semantics(response.document)
    output = dump_tol(response.document)
    print(output)
    if args.echo:
        print(output, file=sys.stderr)
