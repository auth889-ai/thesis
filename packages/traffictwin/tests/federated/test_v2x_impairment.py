"""The impairment adapter is the one thing we add to official federated code, so it is tested
directly — over real sockets, without needing a GPU or the training loop."""
from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
UPSTREAM = Path.home() / ".dhakaflow/upstream/FedGTP"
pytestmark = pytest.mark.skipif(not UPSTREAM.exists(),
                                reason="pinned FedGTP checkout not fetched on this machine")


def _fresh_socket_classes(monkeypatch):
    """Import the upstream socket classes fresh so one test's wrapper cannot leak into another."""
    import sys
    monkeypatch.syspath_prepend(str(UPSTREAM))
    for m in ("lib.client_socket", "lib.server_socket", "lib"):
        sys.modules.pop(m, None)
    from lib.client_socket import ClientSocket
    from lib.server_socket import ServerSocket
    return ClientSocket, ServerSocket


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _exchange(ClientSocket, ServerSocket, port, payloads):
    """One server, one client; the client sends each payload and the server reads it back."""
    got = []

    def serve():
        srv = ServerSocket(1, port, ip="127.0.0.1")
        for _ in payloads:
            got.append(srv.recv(1))
        srv.server_socket.close()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    time.sleep(0.3)
    cli = ClientSocket(1, port, _free_port(), server_ip="127.0.0.1")
    for p in payloads:
        cli.send(p)
    t.join(timeout=20)
    cli.close()
    return got


def test_ideal_profile_delivers_payloads_unchanged(monkeypatch, tmp_path):
    from traffictwin.forecasting.federated import v2x_impairment
    C, S = _fresh_socket_classes(monkeypatch)
    meter = v2x_impairment.install("ideal", role="test", seed=0, repo_on_path=UPSTREAM)
    payloads = [{"w": [1.0, 2.0]}, {"w": [3.0, 4.0]}, {"w": [5.0, 6.0]}]
    got = _exchange(C, S, _free_port(), payloads)
    assert got == payloads, "the control profile must not alter what is delivered"
    assert meter.messages_sent >= len(payloads)
    assert meter.bytes_sent > 0, "byte accounting must record real payload sizes"
    assert meter.dropped_updates == 0
    assert meter.added_delay_s == 0.0


def test_fixed_latency_actually_delays_the_link(monkeypatch):
    from traffictwin.forecasting.federated import v2x_impairment
    C, S = _fresh_socket_classes(monkeypatch)
    meter = v2x_impairment.install("latency_200", role="test", seed=0, repo_on_path=UPSTREAM)
    t0 = time.time()
    got = _exchange(C, S, _free_port(), [{"w": [1.0]}, {"w": [2.0]}])
    elapsed = time.time() - t0
    assert got == [{"w": [1.0]}, {"w": [2.0]}], "delay must not corrupt the payload"
    # every send pays 200 ms; the client's handshake send is wrapped too, so >= 3 sends
    assert meter.added_delay_s >= 0.4, meter.added_delay_s
    assert elapsed >= 0.4, "wall clock must reflect the injected delay, not just the counter"


def test_loss_resends_the_previous_payload_and_counts_the_drop(monkeypatch):
    """A missed deadline must degrade learning by making the aggregator use a STALE update --
    not by corrupting bytes and not by deadlocking the upstream protocol."""
    from traffictwin.forecasting.federated import v2x_impairment
    C, S = _fresh_socket_classes(monkeypatch)
    meter = v2x_impairment.install("loss_50", role="test", seed=7, repo_on_path=UPSTREAM)
    payloads = [{"round": i} for i in range(12)]
    got = _exchange(C, S, _free_port(), payloads)

    assert len(got) == len(payloads), "the protocol must still complete under loss"
    assert meter.dropped_updates > 0, "a 50 % loss profile over 12 rounds must drop something"
    # every delivered value is either the fresh payload or one that was genuinely sent earlier
    for i, g in enumerate(got):
        assert g in payloads[:i + 1], f"delivered {g}, which was never a real payload at or before {i}"
    assert any(g != p for g, p in zip(got, payloads)), "stale substitution never actually happened"


def test_meter_dump_is_machine_readable_and_labels_the_profile(monkeypatch, tmp_path):
    from traffictwin.forecasting.federated import v2x_impairment
    _fresh_socket_classes(monkeypatch)
    meter = v2x_impairment.install("mosaic_v2x", role="client", seed=3, repo_on_path=UPSTREAM)
    out = tmp_path / "meter.json"
    meter.dump(out)
    d = json.loads(out.read_text())
    assert d["profile"] == "mosaic_v2x"
    assert "SIMULATED" in d["measurement_nature"], "the record must never imply hardware measurement"
    assert "MOSAIC" in d["latency_source"] or "mosaic" in d["latency_source"].lower()


def test_unknown_profile_is_refused():
    from traffictwin.forecasting.federated import v2x_impairment
    with pytest.raises(SystemExit):
        v2x_impairment.install("no_such_profile", role="test")
