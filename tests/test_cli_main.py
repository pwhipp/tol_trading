import unittest

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


if __name__ == "__main__":
    unittest.main()
