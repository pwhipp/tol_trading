import unittest

import argparse

from tol.cli.main import build_parser


class TestCliMain(unittest.TestCase):
    def test_run_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "run",
            "example.yaml",
            "--mode",
            "paper",
            "--dry-run",
            "local",
        ])

        self.assertEqual(args.command, "run")
        self.assertEqual(args.tol_file.name, "example.yaml")
        self.assertEqual(args.mode, "paper")
        self.assertEqual(args.dry_run, "local")

    def test_check_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["check", "--mode", "live"])

        self.assertEqual(args.command, "check")
        self.assertEqual(args.mode, "live")

    def test_run_command_default_dry_run(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "example.yaml", "--mode", "paper"])

        self.assertEqual(args.dry_run, None)

    def test_run_help_includes_dry_run_intentions(self) -> None:
        parser = build_parser()
        subparsers_action = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        run_parser = subparsers_action.choices["run"]
        help_text = run_parser.format_help()

        self.assertIn("validates the TOL file only", help_text)
        self.assertIn("queries holdings and prices", help_text)
        self.assertIn("connects to IBKR", help_text)


if __name__ == "__main__":
    unittest.main()
