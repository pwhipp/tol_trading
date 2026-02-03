import sys

from tol.config import get_config
from tol.load import (
    apply_tol_defaults,
    check_tol_syntax_and_static_semantics,
    dump_tol,
)
from tol.llm.client import ChatGptClient


def handle_generate(args) -> None:
    prompt_text = sys.stdin.read()
    if not prompt_text.strip():
        print("ERROR: No natural language request provided on stdin.", file=sys.stderr)
        sys.exit(1)

    client = ChatGptClient.from_config(model_override=args.llm_model)
    config = get_config()

    try:
        response = client.generate_tol(prompt_text)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    for warning in response.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    document = apply_tol_defaults(response.document, mode=config.mode)
    check_tol_syntax_and_static_semantics(document)
    output = dump_tol(document)
    print(output)
    if args.echo:
        print(output, file=sys.stderr)
