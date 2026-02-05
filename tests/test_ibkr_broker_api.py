from unittest.mock import Mock, patch

from ib_insync import Order

from tol.execution.broker.implementations.IBKRBrokerAPI import IBKRBrokerAPI


class _FakeGateway:
    def __init__(self) -> None:
        self.ib = Mock()
        self.connected = False
        self.disconnected = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.disconnected = True


def test_cancel_order_passes_order_object() -> None:
    gateway = _FakeGateway()
    with patch(
        "tol.execution.broker.implementations.IBKRBrokerAPI.IBKRGateway",
        return_value=gateway,
    ):
        broker = IBKRBrokerAPI(mode="paper", client_id=1)
        broker.cancel_order("42")

    gateway.ib.cancelOrder.assert_called_once()
    order = gateway.ib.cancelOrder.call_args[0][0]
    assert isinstance(order, Order)
    assert order.orderId == 42
    assert gateway.connected is True
    assert gateway.disconnected is True
