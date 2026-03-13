"""Tests for Execution Bot main logic."""
from unittest.mock import MagicMock, patch

from services.execution_bot.main import _limit_price, check_open_positions
from services.execution_bot.risk import RiskConfig


def test_limit_price_buy():
    """Buy price is discounted below predicted value."""
    price = _limit_price(0.5, "buy")
    assert price < 0.5
    assert price > 0


def test_limit_price_sell():
    """Sell price is above predicted value."""
    price = _limit_price(0.5, "sell")
    assert price > 0.5


def test_limit_price_edges():
    """Edge cases for limit price calculation."""
    assert _limit_price(0.0, "buy") == 0.0
    assert _limit_price(1.0, "buy") > 0
    assert _limit_price(1.0, "sell") > 1.0


class TestCheckOpenPositions:
    """Tests for stop-loss/take-profit checks."""

    def test_no_positions(self):
        """No positions means no action."""
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = []
        check_open_positions(session, RiskConfig(), dry_run=True)

    @patch("services.execution_bot.main.place_order")
    @patch("services.execution_bot.main.should_stop_loss", return_value=True)
    def test_stop_loss_triggers(self, mock_sl, mock_order):
        """Stop loss triggers closing order."""
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = [
            ("order1", "market1", 0.5, 100, "buy"),
        ]
        session.execute.return_value.fetchone.return_value = (0.3,)
        mock_order.return_value = {"status": "dry_run"}

        check_open_positions(session, RiskConfig(), dry_run=True)
        mock_order.assert_called_once()
        call_kwargs = mock_order.call_args
        assert call_kwargs[1]["side"] == "sell"
        assert call_kwargs[1]["dry_run"] is True

    @patch("services.execution_bot.main.place_order")
    @patch("services.execution_bot.main.should_stop_loss", return_value=False)
    @patch("services.execution_bot.main.should_take_profit", return_value=True)
    def test_take_profit_triggers(self, mock_tp, mock_sl, mock_order):
        """Take profit triggers closing order."""
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = [
            ("order1", "market1", 0.3, 100, "buy"),
        ]
        session.execute.return_value.fetchone.return_value = (0.8,)
        mock_order.return_value = {"status": "dry_run"}

        check_open_positions(session, RiskConfig(), dry_run=True)
        mock_order.assert_called_once()

    @patch("services.execution_bot.main.place_order")
    @patch("services.execution_bot.main.should_stop_loss", return_value=False)
    @patch("services.execution_bot.main.should_take_profit", return_value=False)
    def test_no_trigger(self, mock_tp, mock_sl, mock_order):
        """No trigger = no order placed."""
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = [
            ("order1", "market1", 0.5, 100, "buy"),
        ]
        session.execute.return_value.fetchone.return_value = (0.5,)

        check_open_positions(session, RiskConfig(), dry_run=True)
        mock_order.assert_not_called()

    def test_no_current_price(self):
        """Skip position if no current price available."""
        session = MagicMock()
        positions_result = MagicMock()
        positions_result.fetchall.return_value = [
            ("order1", "market1", 0.5, 100, "buy"),
        ]
        price_result = MagicMock()
        price_result.fetchone.return_value = None
        session.execute.side_effect = [positions_result, price_result]

        check_open_positions(session, RiskConfig(), dry_run=True)
