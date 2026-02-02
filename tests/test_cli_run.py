import unittest

from tol.cli.handlers.run import _extract_mode


class TestCliRun(unittest.TestCase):
    def test_extract_mode_normalizes_valid_mode(self) -> None:
        tol_doc = {"mode": " Live "}

        self.assertEqual(_extract_mode(tol_doc), "live")

    def test_extract_mode_requires_mode(self) -> None:
        with self.assertRaises(ValueError):
            _extract_mode({})

    def test_extract_mode_rejects_invalid_mode(self) -> None:
        with self.assertRaises(ValueError):
            _extract_mode({"mode": "sandbox"})


if __name__ == "__main__":
    unittest.main()
