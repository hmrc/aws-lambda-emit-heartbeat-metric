import unittest

from src import emit_heartbeat_metric


class TestEmitHeartbeatMetric(unittest.TestCase):
    def test_no_alert_percentage(self, mock_open, sys_exit):
        assert "" == 1
