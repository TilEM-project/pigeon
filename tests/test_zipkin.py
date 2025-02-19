from pigeon import Pigeon, BaseMessage
import pytest
from stomp.utils import Frame
from py_zipkin.request_helpers import extract_zipkin_attrs_from_headers
from py_zipkin.util import ZipkinAttrs


class Msg(BaseMessage):
    value: str


@pytest.mark.parametrize(
    "use_zipkin, zipkin_headers, message_headers",
    [
        (
            False,
            {
                "X-B3-TraceId": "trace_id",
                "X-B3-SpanId": "span_id",
                "X-B3-ParentSpanId": "parent_id",
                "X-B3-Sampled": "sample!",
                "X-B3-Flags": "wave!",
            },
            {
                "source": "a name",
                "service": "the service",
                "hostname": "hosty mchostface",
                "pid": 1,
                "hash": "abc123",
                "sent_at": "0",
            },
        ),
        (
            True,
            {
                "X-B3-TraceId": "trace_id",
                "X-B3-SpanId": "span_id",
                "X-B3-ParentSpanId": "parent_id",
                "X-B3-Sampled": "sample!",
                "X-B3-Flags": "wave!",
            },
            {
                "source": "a name",
                "service": "the service",
                "hostname": "hosty mchostface",
                "pid": 1,
                "hash": "abc123",
                "sent_at": "0",
                "X-B3-TraceId": "trace_id",
                "X-B3-SpanId": "span_id",
                "X-B3-ParentSpanId": "parent_id",
                "X-B3-Sampled": "sample!",
                "X-B3-Flags": "wave!",
            },
        ),
        (
            True,
            {},
            {
                "source": "a name",
                "service": "the service",
                "hostname": "hosty mchostface",
                "pid": 1,
                "hash": "abc123",
                "sent_at": "0",
            },
        ),
    ],
)
def test_send_zipkin(mocker, use_zipkin, zipkin_headers, message_headers):
    mocker.patch(
        "pigeon.client.create_http_headers_for_new_span", return_value=zipkin_headers
    )
    mocker.patch("pigeon.client.setup_zipkin_transport", return_value=True)
    mocker.patch("pigeon.client.get_str_time_ms", return_value="0")
    mocker.patch("pigeon.client.stomp.Connection12")

    client = Pigeon("the service", send_zipkin_headers=use_zipkin, load_topics=False)
    client._name = "a name"
    client._hostname = "hosty mchostface"
    client._pid = 1

    client.register_topic("test", Msg)
    client._hashes["test"] = "abc123"

    client.send("test", value="something")

    client._connection.send.assert_called_with(
        destination="test", body='{"value":"something"}', headers=message_headers
    )


@pytest.mark.parametrize(
    "use_zipkin, message_headers, span_created",
    [
        (
            False,
            {
                "X-B3-TraceId": "trace_id",
                "X-B3-SpanId": "span_id",
                "X-B3-ParentSpanId": "parent_id",
                "X-B3-Sampled": "true",
                "X-B3-Flags": "0",
                "source": "a name",
                "service": "the service",
                "hostname": "hosty mchostface",
                "pid": 1,
                "hash": "abc123",
                "sent_at": "0",
                "subscription": "test",
            },
            False,
        ),
        (
            False,
            {
                "source": "a name",
                "service": "the service",
                "hostname": "hosty mchostface",
                "pid": 1,
                "hash": "abc123",
                "sent_at": "0",
                "subscription": "test",
            },
            False,
        ),
        (
            True,
            {
                "X-B3-TraceId": "trace_id",
                "X-B3-SpanId": "span_id",
                "X-B3-ParentSpanId": "parent_id",
                "X-B3-Sampled": "true",
                "X-B3-Flags": "0",
                "source": "a name",
                "service": "the service",
                "hostname": "hosty mchostface",
                "pid": 1,
                "hash": "abc123",
                "sent_at": "0",
                "subscription": "test",
            },
            True,
        ),
        (
            True,
            {
                "source": "a name",
                "service": "the service",
                "hostname": "hosty mchostface",
                "pid": 1,
                "hash": "abc123",
                "sent_at": "0",
                "subscription": "test",
            },
            False,
        ),
    ],
)
def test_receive_zipkin(mocker, use_zipkin, message_headers, span_created):
    mocker.patch("pigeon.client.setup_zipkin_transport")
    mocker.patch("pigeon.client.stomp.Connection12")
    zipkin_span = mocker.patch("pigeon.client.zipkin_span")

    client = Pigeon("the service", create_zipkin_spans=use_zipkin, load_topics=False)

    client.register_topic("test", Msg)
    client._hashes["test"] = "abc123"

    callback = mocker.MagicMock()
    client.subscribe("test", callback)

    msg = Frame("", body='{"value":"something"}', headers=message_headers)

    client._handle_message(msg)

    callback.assert_called_with(Msg(value="something"), "test", message_headers)

    if span_created:
        zipkin_span.assert_called_with(
            service_name=client._service,
            span_name="handle test",
            transport_handler=client._zipkin_transport,
            zipkin_attrs=ZipkinAttrs("trace_id", "span_id", "parent_id", "0", True),
        )
        zipkin_span().__enter__.assert_called()
        zipkin_span().__exit__.assert_called()
    else:
        zipkin_span.assert_not_called()
