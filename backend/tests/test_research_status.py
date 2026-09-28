"""The SYSTEM API exposes computed research gates, including failures."""


def test_research_status_is_evidence_backed(client):
    status = client.get("/api/research/status").json()
    gates = status["gates"]
    assert gates["FORECAST_VALIDATED"]["status"] == "PASSED"
    assert gates["FUTURE_INFORMATION_VALUE"]["status"] == "ESTABLISHED"
    assert gates["PREDICTIVE_CONTROL_VS_REACTIVE"]["status"] == "ESTABLISHED"
    assert gates["LEARNED_FORECAST_ADVANTAGE_VS_PERSISTENCE"]["status"] == "NOT_ESTABLISHED"
    assert gates["DHAKA_DEPLOYMENT_READY"]["status"] == "NOT_READY"
    assert gates["PREDICTIVE_TRAFFIC_BENEFIT"]["status"] == "NOT_ESTABLISHED"
