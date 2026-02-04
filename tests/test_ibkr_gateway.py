import io
import unittest
from contextlib import redirect_stdout

from ib_insync.wrapper import RequestError

from tol.ibkr.gateway import IBKRGateway


class _FakeIB:
    def __init__(self, error: RequestError) -> None:
        self._error = error
        self.disconnected = False

    def isConnected(self) -> bool:
        return False

    def connect(self, *_args, **_kwargs) -> None:
        raise self._error

    def disconnect(self) -> None:
        self.disconnected = True


class TestIBKRGatewayConnect(unittest.TestCase):
    def test_client_id_in_use_prints_message(self) -> None:
        gateway = IBKRGateway("paper", client_id=7)
        error = RequestError(reqId=1, code=326, message="client id conflict")
        gateway.ib = _FakeIB(error)

        stdout = io.StringIO()
        with self.assertRaises(RequestError):
            with redirect_stdout(stdout):
                gateway.connect()

        self.assertTrue(gateway.ib.disconnected)
        self.assertEqual(
            stdout.getvalue().strip(),
            "clientId (7) already in use.\n"
            "Try a different clientId or restart the IB Gateway process.",
        )
