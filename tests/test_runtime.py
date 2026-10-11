"""Check event subscription acceptance and framing without a live server."""

import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from runtime import Events


def frame(value):
    return (json.dumps(value) + "\n").encode()


class EventSubscriptions(unittest.TestCase):
    def test_rejected_subscription_fails_before_periodic_reconciliation(self):
        connection = Mock()
        connection.recv.return_value = frame({"error": {"code": "invalid_request"}})
        with patch("runtime.socket.socket", return_value=connection):
            with self.assertRaisesRegex(RuntimeError, "events.subscribe: invalid_request"):
                Events(SimpleNamespace(socket="/unused/socket"))
        connection.close.assert_called_once()

    def test_event_received_with_ack_is_delivered_without_another_read(self):
        connection = Mock()
        connection.recv.return_value = (
            frame({"result": {"type": "subscription_started"}})
            + frame({"event": "workspace.renamed", "data": {"workspace_id": "w1"}})
        )
        with patch("runtime.socket.socket", return_value=connection):
            events = Events(SimpleNamespace(socket="/unused/socket"))
        try:
            with patch("runtime.select.select", return_value=([], [], [])):
                self.assertTrue(events.dirty())
                self.assertFalse(events.dirty())
            connection.recv.assert_called_once()
        finally:
            events.close()


if __name__ == "__main__":
    unittest.main()
