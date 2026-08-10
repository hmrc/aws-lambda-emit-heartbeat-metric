import datetime
from unittest import mock

import pytest

from src import emit_heartbeat_metric


@pytest.mark.parametrize(
    "minute,expected_val",
    [
        (0, 0),
        (1, 0),
        (2, 1),
        (3, 1),
        (4, 0),
        (59, 1),
    ],
)
@mock.patch("src.emit_heartbeat_metric.graphyte")
@mock.patch("src.emit_heartbeat_metric.datetime")
def test_lambda_handler_sends_expected_value_for_minute(
    mock_datetime, mock_graphyte, minute, expected_val
):
    fixed_time = datetime.datetime(2026, 8, 10, 12, minute, 0)
    mock_datetime.datetime.now.return_value = fixed_time

    emit_heartbeat_metric.lambda_handler({}, None)

    mock_graphyte.send.assert_called_once_with(
        metric="metrics.alerting.heartbeat",
        value=expected_val,
        timestamp=fixed_time.timestamp(),
    )


@mock.patch("src.emit_heartbeat_metric.graphyte")
@mock.patch("src.emit_heartbeat_metric.datetime")
def test_lambda_handler_uses_default_env_vars(
    mock_datetime, mock_graphyte, monkeypatch
):
    monkeypatch.delenv("GRAPHITE_HOST", raising=False)
    monkeypatch.delenv("GRAPHITE_METRIC_PREFIX", raising=False)
    mock_datetime.datetime.now.return_value = datetime.datetime(2026, 8, 10, 12, 0, 0)

    emit_heartbeat_metric.lambda_handler({}, None)

    mock_graphyte.init.assert_called_once_with(
        host="graphite-collectd", prefix="telemetry", timeout=1
    )


@mock.patch("src.emit_heartbeat_metric.graphyte")
@mock.patch("src.emit_heartbeat_metric.datetime")
def test_lambda_handler_uses_env_vars_when_set(
    mock_datetime, mock_graphyte, monkeypatch
):
    monkeypatch.setenv("GRAPHITE_HOST", "custom-host")
    monkeypatch.setenv("GRAPHITE_METRIC_PREFIX", "custom-prefix")
    mock_datetime.datetime.now.return_value = datetime.datetime(2026, 8, 10, 12, 0, 0)

    emit_heartbeat_metric.lambda_handler({}, None)

    mock_graphyte.init.assert_called_once_with(
        host="custom-host", prefix="custom-prefix", timeout=1
    )
