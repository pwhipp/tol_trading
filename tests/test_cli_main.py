import unittest

import argparse

from tol.cli.main import build_parser


class TestCliMain(unittest.TestCase):
    def test_run_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "run",
            "--mode",
            "paper",
            "--dry-run",
            "local",
        ])

        self.assertEqual(args.command, "run")
        self.assertEqual(args.mode, "paper")
        self.assertEqual(args.dry_run, "local")

    def test_check_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["check", "--mode", "live"])

        self.assertEqual(args.command, "check")
        self.assertEqual(args.mode, "live")

    def test_run_command_default_dry_run(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "--mode", "paper"])

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

    def test_describe_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["describe"])

        self.assertEqual(args.command, "describe")
        self.assertIsNone(args.llm_model)

    def test_generate_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["generate", "--llm-model", "gpt-4o-mini"])

        self.assertEqual(args.command, "generate")
        self.assertEqual(args.llm_model, "gpt-4o-mini")

    def test_config_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["config", "get", "model"])

        self.assertEqual(args.command, "config")
        self.assertEqual(args.config_command, "get")
        self.assertEqual(args.key, "model")


if __name__ == "__main__":
    unittest.main()
