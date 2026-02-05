import sys

from tol.cli.build_parser import build_parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = getattr(args, "handler", None)

    if handler is None:
        parser.error(f"Unknown command - {args.command}")

    try:
        handler(args)
    except ConnectionRefusedError:  # gateway reports the connection error to stderr already
        sys.exit(1)
