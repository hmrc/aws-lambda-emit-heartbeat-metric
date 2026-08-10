import socket
from unittest import mock

import pytest

from src import graphyte


class TestHasWhitespace:
    def test_empty_string_counts_as_whitespace(self):
        assert graphyte._has_whitespace("") is True

    def test_no_whitespace(self):
        assert graphyte._has_whitespace("metric.name") is False

    def test_with_whitespace(self):
        assert graphyte._has_whitespace("metric name") is True


class TestBuildMessage:
    def test_basic_message(self):
        sender = graphyte.Sender("localhost")
        message = sender.build_message("my.metric", 1, 1000)
        assert message == b"my.metric 1 1000\n"

    def test_with_prefix(self):
        sender = graphyte.Sender("localhost", prefix="prefix")
        message = sender.build_message("my.metric", 1, 1000)
        assert message == b"prefix.my.metric 1 1000\n"

    def test_with_tags(self):
        sender = graphyte.Sender("localhost", tags={"a": "1"})
        message = sender.build_message("my.metric", 1, 1000, tags={"b": "2"})
        assert message == b"my.metric;a=1;b=2 1 1000\n"

    def test_tags_override_default_tags(self):
        sender = graphyte.Sender("localhost", tags={"a": "1"})
        message = sender.build_message("my.metric", 1, 1000, tags={"a": "2"})
        assert message == b"my.metric;a=2 1 1000\n"

    def test_rounds_timestamp(self):
        sender = graphyte.Sender("localhost")
        message = sender.build_message("my.metric", 1, 1000.6)
        assert message == b"my.metric 1 1001\n"

    def test_metric_with_whitespace_raises(self):
        sender = graphyte.Sender("localhost")
        with pytest.raises(ValueError):
            sender.build_message("my metric", 1, 1000)

    def test_non_numeric_value_raises(self):
        sender = graphyte.Sender("localhost")
        with pytest.raises(TypeError):
            sender.build_message("my.metric", "not-a-number", 1000)

    def test_tag_with_whitespace_raises(self):
        sender = graphyte.Sender("localhost", tags={"a b": "1"})
        with pytest.raises(ValueError):
            sender.build_message("my.metric", 1, 1000)


class TestSend:
    def test_send_uses_current_time_if_not_given(self):
        sender = graphyte.Sender("localhost")
        with (
            mock.patch.object(sender, "send_socket") as mock_send_socket,
            mock.patch("src.graphyte.time.time", return_value=1000),
        ):
            sender.send("my.metric", 1)
        mock_send_socket.assert_called_once_with(b"my.metric 1 1000\n")

    def test_send_synchronous_calls_send_socket(self):
        sender = graphyte.Sender("localhost")
        with mock.patch.object(sender, "send_socket") as mock_send_socket:
            sender.send("my.metric", 1, timestamp=1000)
        mock_send_socket.assert_called_once_with(b"my.metric 1 1000\n")


class TestSendMessage:
    def test_tcp_protocol(self):
        sender = graphyte.Sender("localhost", port=2003, protocol="tcp")
        mock_sock = mock.MagicMock()
        with mock.patch(
            "src.graphyte.socket.create_connection", return_value=mock_sock
        ) as mock_create:
            sender.send_message(b"my.metric 1 1000\n")
        mock_create.assert_called_once_with(("localhost", 2003), sender.timeout)
        mock_sock.sendall.assert_called_once_with(b"my.metric 1 1000\n")
        mock_sock.close.assert_called_once()

    def test_udp_protocol(self):
        sender = graphyte.Sender("localhost", port=2003, protocol="udp")
        mock_sock = mock.MagicMock()
        with mock.patch("src.graphyte.socket.socket", return_value=mock_sock):
            sender.send_message(b"my.metric 1 1000\n")
        mock_sock.sendto.assert_called_once_with(
            b"my.metric 1 1000\n", ("localhost", 2003)
        )
        mock_sock.close.assert_called_once()

    def test_invalid_protocol_raises(self):
        sender = graphyte.Sender("localhost", protocol="bogus")
        with pytest.raises(ValueError):
            sender.send_message(b"my.metric 1 1000\n")

    def test_tcp_socket_closed_on_send_error(self):
        sender = graphyte.Sender("localhost", protocol="tcp")
        mock_sock = mock.MagicMock()
        mock_sock.sendall.side_effect = OSError("boom")
        with mock.patch(
            "src.graphyte.socket.create_connection", return_value=mock_sock
        ):
            with pytest.raises(OSError):
                sender.send_message(b"my.metric 1 1000\n")
        mock_sock.close.assert_called_once()


class TestSendSocket:
    def test_swallows_error_by_default(self):
        sender = graphyte.Sender("localhost")
        with mock.patch.object(
            sender, "send_message", side_effect=socket.error("boom")
        ):
            sender.send_socket(b"my.metric 1 1000\n")

    def test_raises_when_configured(self):
        sender = graphyte.Sender("localhost", raise_send_errors=True)
        with mock.patch.object(
            sender, "send_message", side_effect=socket.error("boom")
        ):
            with pytest.raises(socket.error):
                sender.send_socket(b"my.metric 1 1000\n")

    def test_logs_on_success_when_log_sends_enabled(self):
        sender = graphyte.Sender("localhost", log_sends=True)
        with (
            mock.patch.object(sender, "send_message") as mock_send_message,
            mock.patch("src.graphyte.logger") as mock_logger,
        ):
            sender.send_socket(b"my.metric 1 1000\n")
        mock_send_message.assert_called_once()
        mock_logger.info.assert_called_once()


class TestSenderInit:
    def test_raise_send_errors_incompatible_with_interval(self):
        with pytest.raises(ValueError):
            graphyte.Sender("localhost", interval=1, raise_send_errors=True)

    def test_interval_mode_starts_background_thread(self):
        sender = graphyte.Sender("localhost", interval=60)
        try:
            assert sender._thread.is_alive()
        finally:
            sender.stop()

    def test_interval_mode_default_queue_size(self):
        sender = graphyte.Sender("localhost", interval=2)
        try:
            assert sender._queue.maxsize == 200
        finally:
            sender.stop()

    def test_interval_mode_send_and_stop_flushes_queue(self):
        sender = graphyte.Sender("localhost", interval=60)
        with mock.patch.object(sender, "send_socket") as mock_send_socket:
            sender.send("my.metric", 1, timestamp=1000)
            sender.stop()
        mock_send_socket.assert_called_once_with(b"my.metric 1 1000\n")

    def test_stop_is_a_noop_when_not_in_interval_mode(self):
        sender = graphyte.Sender("localhost")
        sender.stop()


class TestModuleLevelHelpers:
    def test_init_creates_default_sender(self):
        graphyte.init("localhost", prefix="prefix")
        try:
            assert isinstance(graphyte.default_sender, graphyte.Sender)
            assert graphyte.default_sender.host == "localhost"
            assert graphyte.default_sender.prefix == "prefix"
        finally:
            graphyte.default_sender = None

    def test_send_delegates_to_default_sender(self):
        graphyte.default_sender = mock.MagicMock()
        try:
            graphyte.send("my.metric", 1, timestamp=1000)
            graphyte.default_sender.send.assert_called_once_with(
                "my.metric", 1, timestamp=1000
            )
        finally:
            graphyte.default_sender = None
