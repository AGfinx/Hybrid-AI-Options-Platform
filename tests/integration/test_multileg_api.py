import json
import pytest
from fastapi.testclient import TestClient
from services.api.main import app
from db.database import SessionLocal
from db.models import Recommendation, Instrument, QuoteSnapshot

client = TestClient(app)

def test_multi_asset_instruments_and_surface():
    """Verify ETH instruments and volatility surface are accessible."""
    # ETH Instruments
    resp = client.get("/api/v1/instruments?underlying=ETH")
    assert resp.status_code == 200
    instruments = resp.json()["data"]
    assert len(instruments) > 0
    assert all(i["underlying"] == "ETH" for i in instruments)

    # ETH Volatility Surface with SVI slices
    resp_surf = client.get("/api/v1/surfaces/ETH")
    assert resp_surf.status_code == 200
    surf_data = resp_surf.json()["data"]
    assert surf_data["underlying"] == "ETH"
    assert "svi_slices" in surf_data
    assert "points" in surf_data

def test_multi_leg_generation_and_watchlist():
    """Verify opportunity generation creates multi-leg straddles/calendars and watchlist toggle functions."""
    # Trigger generation for both BTC and ETH
    gen_resp = client.post("/api/v1/recommendations/generate")
    assert gen_resp.status_code == 200
    data = gen_resp.json()["data"]
    assert data["generated_count"] > 0

    # Query recommendations
    rec_resp = client.get("/api/v1/recommendations")
    assert rec_resp.status_code == 200
    recs = rec_resp.json()["data"]
    assert len(recs) > 0

    # Check for multi-leg strategies
    strategy_types = [r["strategy_type"] for r in recs]
    assert any("straddle" in st or "calendar" in st for st in strategy_types)

    # Test Watchlist Toggle
    target_rec = recs[0]
    rec_id = target_rec["id"]
    init_watchlist = target_rec["is_watchlist"]

    toggle_resp = client.post(f"/api/v1/recommendations/{rec_id}/watchlist")
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["data"]["is_watchlist"] == (not init_watchlist)

    # Query with watchlist_only=true
    wl_resp = client.get("/api/v1/recommendations?watchlist_only=true")
    assert wl_resp.status_code == 200
    wl_recs = wl_resp.json()["data"]
    if not init_watchlist:
        assert any(r["id"] == rec_id for r in wl_recs)
        assert all(r["is_watchlist"] is True for r in wl_recs)

def test_atomic_multi_leg_approval():
    """Verify approving a multi-leg recommendation creates orders and executes atomically."""
    rec_resp = client.get("/api/v1/recommendations")
    recs = rec_resp.json()["data"]
    
    # Find a pending multi-leg recommendation (or pending single leg)
    pending_rec = next((r for r in recs if r["status"] == "pending" and len(r["legs"]) > 1), None)
    if not pending_rec:
        pending_rec = next((r for r in recs if r["status"] == "pending"), None)
    
    assert pending_rec is not None, "A pending recommendation should be available"
    rec_id = pending_rec["id"]

    approve_resp = client.post(
        f"/api/v1/recommendations/{rec_id}/approve",
        json={"comment": "Milestone 2 multi-leg automated test approval"}
    )
    assert approve_resp.status_code == 200
    appr_data = approve_resp.json()["data"]
    assert appr_data["status"] == "approved"
    assert "paper_order_id" in appr_data
    assert "execution" in appr_data
    assert appr_data["execution"]["status"] == "filled"

def test_portfolio_delta_rebalance_endpoint():
    """Verify delta drift rebalancing endpoint responds correctly."""
    rebal_resp = client.post("/api/v1/portfolio/rebalance?underlying=BTC")
    assert rebal_resp.status_code == 200
    data = rebal_resp.json()["data"]
    assert "status" in data
    assert data["status"] in ["within_tolerance", "rebalanced"]
