from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from another_box.errors import SubscriptionError
from another_box.subscriptions import SubscriptionClient


class JsonHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"outbounds": [{"type": "direct"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


def test_subscription_client_with_local_http_server(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    server = ThreadingHTTPServer(("127.0.0.1", 0), JsonHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        result = SubscriptionClient(timeout=2).fetch(f"http://{host}:{port}/config")
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert result["outbounds"][0]["type"] == "direct"


@pytest.mark.parametrize(
    ("section", "body"),
    [
        (
            "outbounds",
            '{"outbounds": [{"tag": "first"}], "outbounds": [{"tag": "second"}]}',
        ),
        (
            "dns",
            '{"dns": {"servers": []}, "dns": {"servers": [{"type": "local"}]}}',
        ),
    ],
)
def test_subscription_client_rejects_duplicate_json_options(section, body):
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=body.encode())
    )

    with pytest.raises(SubscriptionError, match=rf"Повторяющаяся опция JSON: «{section}»"):
        SubscriptionClient(transport=transport).fetch("https://example.test/config")
