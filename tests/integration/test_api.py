import pytest
from fastapi.testclient import TestClient
from services.api.main import app

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

def test_root_endpoint(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "operational"
    assert data["mode"] == "recommendation"
    assert data["live_trading_enabled"] is False

def test_market_health(client):
    res = client.get("/api/v1/market/health")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "venue" in data
    assert "is_connected" in data
    assert data["live_feed_enabled"] is False

def test_instruments(client):
    res = client.get("/api/v1/instruments?underlying=BTC")
    assert res.status_code == 200
    instruments = res.json()["data"]
    assert len(instruments) > 0
    assert instruments[0]["underlying"] == "BTC"

def test_volatility_surface(client):
    res = client.get("/api/v1/surfaces/BTC")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["underlying"] == "BTC"
    assert data["structural_status"] in ["valid", "arbitrage_violated", "fallback"]

def test_rv_forecast(client):
    res = client.post("/api/v1/forecasts/realized-volatility", json={"underlying": "BTC", "horizon_seconds": 3600})
    assert res.status_code == 200
    data = res.json()["data"]
    assert "forecast" in data
    assert data["regime"] in ["low", "normal", "elevated", "extreme"]

def test_recommendation_lifecycle(client):
    # 1. Generate
    gen_res = client.post("/api/v1/recommendations/generate")
    assert gen_res.status_code == 200

    # 2. List
    list_res = client.get("/api/v1/recommendations")
    assert list_res.status_code == 200
    recs = list_res.json()["data"]
    assert len(recs) > 0

    target = recs[0]
    rec_id = target["id"]

    # 3. Edit
    edit_res = client.post(f"/api/v1/recommendations/{rec_id}/edit", json={"quantity": 2.0, "edit_reason": "Adjust sizing"})
    assert edit_res.status_code == 200
    assert edit_res.json()["data"]["greeks"]["delta"] != 0

    # 4. Reject another rec to test reject flow
    if len(recs) > 1:
        other_id = recs[1]["id"]
        rej_res = client.post(f"/api/v1/recommendations/{other_id}/reject", json={"reason": "Spread too wide"})
        assert rej_res.status_code == 200
        assert rej_res.json()["data"]["status"] == "rejected"

    # 5. Approve
    appr_res = client.post(f"/api/v1/recommendations/{rec_id}/approve", json={"mode": "paper", "comment": "Approved after review"})
    assert appr_res.status_code in [200, 409] # 200 if fresh, 409 if already approved

def test_mandates(client):
    list_res = client.get("/api/v1/mandates")
    assert list_res.status_code == 200
    mandates = list_res.json()["data"]
    assert len(mandates) > 0

def test_portfolio_risk_and_stress(client):
    risk_res = client.get("/api/v1/portfolio/risk")
    assert risk_res.status_code == 200
    data = risk_res.json()["data"]
    assert "total_capital" in data
    assert "greeks" in data
    assert "circuit_breakers" in data

    stress_res = client.post("/api/v1/risk/stress-runs", json={"target_type": "portfolio"})
    assert stress_res.status_code == 200
    assert "results" in stress_res.json()["data"]

def test_emergency_stop_and_safety_fail_closed(client):
    # Trip emergency stop
    stop_res = client.post("/api/v1/controls/emergency-stop", json={"reason": "Integration test safety drill", "confirmed": True})
    assert stop_res.status_code == 200
    assert stop_res.json()["data"]["status"] == "emergency_stop_active"

    # Verify paper order fails closed
    insts = client.get("/api/v1/instruments").json()["data"]
    inst_id = insts[0]["id"]
    order_res = client.post("/api/v1/paper/orders", json={"instrument_id": inst_id, "direction": "buy", "quantity": 1.0})
    assert order_res.status_code == 422
    assert "Emergency Stop is active" in order_res.json()["detail"]

    # Reset emergency stop
    reset_res = client.post("/api/v1/controls/emergency-stop/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["data"]["status"] == "normal"

def test_paper_orders_and_positions(client):
    orders_res = client.get("/api/v1/paper/orders")
    assert orders_res.status_code == 200
    positions_res = client.get("/api/v1/paper/positions")
    assert positions_res.status_code == 200

def test_pnl_report_and_audit_log(client):
    pnl_res = client.get("/api/v1/reports/pnl")
    assert pnl_res.status_code == 200
    assert "total_pnl" in pnl_res.json()["data"]

    audit_res = client.get("/api/v1/audit/events")
    assert audit_res.status_code == 200
    events = audit_res.json()["data"]
    assert len(events) > 0
    assert any(e["action"] in ["emergency_stop_tripped", "approve_recommendation"] for e in events)

def test_operating_mode_control(client):
    mode_res = client.get("/api/v1/controls/mode")
    assert mode_res.status_code == 200
    assert mode_res.json()["data"]["live_trading_enabled"] is False

    switch_res = client.post("/api/v1/controls/mode", json={"mode": "analytics", "reason": "Testing mode switch"})
    assert switch_res.status_code == 200
    assert switch_res.json()["data"]["operating_mode"] == "analytics"

    # Switch back to recommendation mode
    client.post("/api/v1/controls/mode", json={"mode": "recommendation"})
