import unittest

import argparse

from tol.cli.main import build_parser


class TestCliMain(unittest.TestCase):
    def test_run_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "run",
            "example.yaml",
        ])

        self.assertEqual(args.command, "run")
        self.assertEqual(args.file, "example.yaml")

    def test_check_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["check", "--mode", "live"])

        self.assertEqual(args.command, "check")
        self.assertEqual(args.mode, "live")

    def test_run_command_default_dry_run(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "example.yaml"])

        self.assertEqual(args.file, "example.yaml")

    def test_run_help_mentions_file(self) -> None:
        parser = build_parser()
        subparsers_action = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        run_parser = subparsers_action.choices["run"]
        help_text = run_parser.format_help()

        self.assertIn("Path to the TOL document", help_text)

    def test_describe_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["describe"])

        self.assertEqual(args.command, "describe")
        self.assertIsNone(args.llm_model)

    def test_generate_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["generate", "--mode", "live", "--llm-model", "gpt-5", "--echo"]
        )

        self.assertEqual(args.command, "generate")
        self.assertEqual(args.mode, "live")
        self.assertEqual(args.llm_model, "gpt-5")
        self.assertTrue(args.echo)

    def test_config_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["config", "get", "model"])

        self.assertEqual(args.command, "config")
        self.assertEqual(args.config_command, "get")
        self.assertEqual(args.key, "model")

    def test_test_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["test", "--echo"])

        self.assertEqual(args.command, "test")
        self.assertTrue(args.echo)

    def test_resume_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["resume"])

        self.assertEqual(args.command, "resume")

    def test_status_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["status", "12"])

        self.assertEqual(args.command, "status")
        self.assertEqual(args.execution_id, 12)

    def test_abort_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["abort", "7"])

        self.assertEqual(args.command, "abort")
        self.assertEqual(args.execution_id, 7)

    def test_status_command_without_db_schema(self) -> None:
        import os
        import tempfile

        from tol.llm import config as llm_config
        from tol.cli.handlers.status import handle_status

        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["XDG_CONFIG_HOME"] = temp_dir
            settings = llm_config.load_settings()
            updated = llm_config.set_setting(settings, "broker", "FakeBrokerAPI")
            llm_config.write_settings(updated)
            try:
                args = build_parser().parse_args(["status"])
                handle_status(args)
            finally:
                os.environ.pop("XDG_CONFIG_HOME", None)


if __name__ == "__main__":
    unittest.main()
