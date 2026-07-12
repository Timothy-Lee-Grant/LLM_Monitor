"""Metrics tests (plan 002 Step 4). Single-process registry in tests (no
PROMETHEUS_MULTIPROC_DIR), so counter values read back directly from REGISTRY.
"""

from prometheus_client import REGISTRY


def _sample_value(name: str, labels: dict) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_metrics_endpoint_serves_prometheus_format(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "llm_request" in response.get_data(as_text=True)


def test_dispatch_increments_labeled_counters(client):
    before = _sample_value("llm_requests_total", {"pipeline_id": "chat-basic", "status": "success"})

    assert client.post("/chat/basic", json={"user_message": "hi"}).status_code == 200

    after = _sample_value("llm_requests_total", {"pipeline_id": "chat-basic", "status": "success"})
    assert after == before + 1
