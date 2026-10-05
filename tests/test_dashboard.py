import json
import threading
import urllib.error
import urllib.request
from datetime import datetime
from http.server import ThreadingHTTPServer

from test_engine import FakeData, at, make_cfg

from zerodhatrades.broker.paper import PaperBroker
from zerodhatrades.dashboard import build_state, make_handler
from zerodhatrades.engine import IST, Engine


def test_build_state_after_trade(tmp_path):
    cfg = make_cfg(tmp_path)
    data = FakeData([101.0], 1000.0)
    eng = Engine(cfg, PaperBroker(data))
    eng.tick(at(10, 0))
    s = build_state(cfg, at(10, 1))
    assert len(s["positions"]) == 1 and s["day_pnl"] == 0
    data.price = 1020.0
    eng.tick(at(10, 5))
    s = build_state(cfg, at(10, 6))
    assert s["day_pnl"] == 200 and not s["positions"]
    assert s["events"][0]["event"] == "exit"
    assert s["heartbeat_age_s"] == 60


def test_http_state_and_kill_switch(tmp_path):
    cfg = make_cfg(tmp_path)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cfg))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    try:
        assert b"ZerodhaTrades" in urllib.request.urlopen(base + "/").read()
        st = json.load(urllib.request.urlopen(base + "/api/state"))
        assert st["kill_switch"] is False and st["mode"] == "paper"

        def post(headers):
            req = urllib.request.Request(base + "/api/kill", json.dumps({"on": True}).encode(),
                                         headers=headers, method="POST")
            return urllib.request.urlopen(req)

        try:
            post({})  # missing X-ZT header => rejected
            raise AssertionError("expected 403")
        except urllib.error.HTTPError as e:
            assert e.code == 403
        assert not (tmp_path / "KILL").exists()
        post({"X-ZT": "1"})
        assert (tmp_path / "KILL").exists()
        req = urllib.request.Request(base + "/api/state", headers={"Host": "evil.example"})
        try:
            urllib.request.urlopen(req)
            raise AssertionError("expected 403")
        except urllib.error.HTTPError as e:
            assert e.code == 403
    finally:
        srv.shutdown()


def test_state_with_no_files(tmp_path):
    s = build_state(make_cfg(tmp_path), datetime(2026, 10, 5, 9, 0, tzinfo=IST))
    assert s["positions"] == [] and s["heartbeat_age_s"] is None
