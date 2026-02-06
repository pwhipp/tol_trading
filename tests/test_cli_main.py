import unittest

import argparse

from tol.cli.main import build_parser


class TestCliMain(unittest.TestCase):
    def test_execute_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "execute",
        ])

        self.assertEqual(args.command, "execute")
        self.assertEqual(args.execute_command, "run")

    def test_broker_summary_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["broker", "summary"])

        self.assertEqual(args.command, "broker")
        self.assertEqual(args.broker_command, "summary")

    def test_broker_orders_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["broker", "orders"])

        self.assertEqual(args.command, "broker")
        self.assertEqual(args.broker_command, "orders")

    def test_broker_price_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["broker", "price", "MSFT"])

        self.assertEqual(args.command, "broker")
        self.assertEqual(args.broker_command, "price")
        self.assertEqual(args.tickers, ["MSFT"])
        self.assertEqual(args.watch, "reset")

    def test_broker_price_command_parsing_without_tickers(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["broker", "price"])

        self.assertEqual(args.command, "broker")
        self.assertEqual(args.broker_command, "price")
        self.assertEqual(args.tickers, [])
        self.assertEqual(args.watch, "reset")

    def test_execute_command_default_run(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["execute"])

        self.assertEqual(args.command, "execute")
        self.assertEqual(args.execute_command, "run")

    def test_execute_run_dry_run_flag_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["execute", "run", "--dry-run"])

        self.assertEqual(args.command, "execute")
        self.assertEqual(args.execute_command, "run")
        self.assertTrue(args.dry_run)

    def test_execute_help_mentions_stdin(self) -> None:
        parser = build_parser()
        subparsers_action = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        execute_parser = subparsers_action.choices["execute"]
        help_text = execute_parser.format_help()

        self.assertIn("usage: tol execute", help_text)
        self.assertIn("Execute a TOL orchestration from stdin.", help_text)

    def test_describe_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["describe"])

        self.assertEqual(args.command, "describe")
        self.assertIsNone(args.llm_model)

    def test_generate_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["generate", "--llm-model", "gpt-5", "--echo"]
        )

        self.assertEqual(args.command, "generate")
        self.assertEqual(args.llm_model, "gpt-5")
        self.assertTrue(args.echo)

    def test_config_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["config", "get", "model"])

        self.assertEqual(args.command, "config")
        self.assertEqual(args.config_command, "get")
        self.assertEqual(args.key, "model")

    def test_execute_resume_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["execute", "resume"])

        self.assertEqual(args.command, "execute")
        self.assertEqual(args.execute_command, "resume")

    def test_execute_status_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["execute", "status", "12"])

        self.assertEqual(args.command, "execute")
        self.assertEqual(args.execute_command, "status")
        self.assertEqual(args.execution_id, 12)

    def test_execute_cancel_command_parsing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["execute", "cancel", "7"])

        self.assertEqual(args.command, "execute")
        self.assertEqual(args.execute_command, "cancel")
        self.assertEqual(args.execution_id, 7)


    def test_config_default_subcommand_is_show(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["config"])

        self.assertEqual(args.command, "config")
        self.assertEqual(args.config_command, "show")

    def test_execute_help_lists_nested_subcommands(self) -> None:
        parser = build_parser()
        subparsers_action = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        execute_parser = subparsers_action.choices["execute"]
        help_text = execute_parser.format_help()

        self.assertIn("run", help_text)
        self.assertIn("status", help_text)

    def test_status_command_without_db_schema(self) -> None:
        import os
        import tempfile

        from tol import config as app_config
        from tol.cli.handlers.execute.status import handle_execute_status

        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["XDG_CONFIG_HOME"] = temp_dir
            app_config.get_config.cache_clear()
            settings = app_config.get_config()
            updated = app_config.set_setting(settings, "broker", "FakeBrokerAPI")
            updated.save()
            try:
                args = build_parser().parse_args(["execute", "status"])
                handle_execute_status(args)
            finally:
                os.environ.pop("XDG_CONFIG_HOME", None)


if __name__ == "__main__":
    unittest.main()
