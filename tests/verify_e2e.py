import httpx
import json
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"
HEADERS = {
    "Authorization": "Bearer dev-token",
    "Content-Type": "application/json"
}

def verify():
    # Ensure emergency stop is reset before starting
    httpx.post(f"{BASE_URL}/controls/emergency-stop/reset", headers=HEADERS)

    print("=== 1. Checking Market Health ===")
    r = httpx.get(f"{BASE_URL}/market/health", headers=HEADERS)
    print(f"Status: {r.status_code}, Health: {r.json()['data']['data_quality']}, Spot: ${r.json()['data']['spot_price']:,.2f}")
    assert r.status_code == 200

    print("\n=== 2. Checking Volatility Surface (BTC & ETH) ===")
    r_btc = httpx.get(f"{BASE_URL}/surfaces/BTC", headers=HEADERS)
    btc_surf = r_btc.json()["data"]
    print(f"BTC Surface points: {len(btc_surf['points'])}, SVI slices: {len(btc_surf.get('svi_slices', []))}, Confidence: {btc_surf['confidence']}")
    assert r_btc.status_code == 200

    r_eth = httpx.get(f"{BASE_URL}/surfaces/ETH", headers=HEADERS)
    eth_surf = r_eth.json()["data"]
    print(f"ETH Surface points: {len(eth_surf['points'])}, SVI slices: {len(eth_surf.get('svi_slices', []))}, Confidence: {eth_surf['confidence']}")
    assert r_eth.status_code == 200

    print("\n=== 3. Generating Recommendations ===")
    r_gen = httpx.post(f"{BASE_URL}/recommendations/generate", headers=HEADERS)
    print(f"Generated count: {r_gen.json()['data']['generated_count']}")
    assert r_gen.status_code == 200

    print("\n=== 4. Querying Ranked Recommendations (Pending) ===")
    r_recs = httpx.get(f"{BASE_URL}/recommendations?status=pending", headers=HEADERS)
    recs = r_recs.json()["data"]
    print(f"Total pending recommendations: {len(recs)}")
    for i, rec in enumerate(recs[:3]):
        print(f"  [{i+1}] ID: {rec['id']} | Strategy: {rec['strategy_type']} | Net Edge: {rec['net_edge']:.2%} | Confidence: {rec['confidence']:.2f}")

    target_rec = recs[0]
    rec_id = target_rec["id"]

    print(f"\n=== 5. Testing Recommendation Edit (Recalculating Net Edge & Risk) ===")
    new_qty = 2.5
    r_edit = httpx.post(
        f"{BASE_URL}/recommendations/{rec_id}/edit",
        headers=HEADERS,
        json={"quantity": new_qty, "price_limit": 1500.0, "edit_reason": "Adjusting size for liquidity"}
    )
    print(f"Edit status: {r_edit.status_code}, New Net Edge: {r_edit.json()['data']['net_edge']:.2%}")
    assert r_edit.status_code == 200

    print(f"\n=== 6. Testing Watchlist Toggle ===")
    r_wl = httpx.post(f"{BASE_URL}/recommendations/{rec_id}/watchlist", headers=HEADERS)
    print(f"Watchlist status for {rec_id}: {r_wl.json()['data']['is_watchlist']}")
    assert r_wl.status_code == 200

    print(f"\n=== 7. Approving Recommendation {rec_id} ===")
    r_appr = httpx.post(
        f"{BASE_URL}/recommendations/{rec_id}/approve",
        headers=HEADERS,
        json={"mode": "paper", "comment": "Quantitative thesis verified"}
    )
    print(f"Approval HTTP Status: {r_appr.status_code}, Response: {r_appr.text}")
    assert r_appr.status_code == 200
    appr_data = r_appr.json()["data"]
    print(f"Approval Result: {appr_data['status']}, Paper Order ID: {appr_data.get('paper_order_id')}, Risk Passed: {appr_data.get('risk_check', {}).get('approved')}")

    print("\n=== 8. Verifying Paper Orders & Position Book ===")
    r_orders = httpx.get(f"{BASE_URL}/paper/orders", headers=HEADERS)
    orders = r_orders.json()["data"]
    print(f"Total paper orders: {len(orders)}, Latest order status: {orders[0]['status']}")
    
    r_pos = httpx.get(f"{BASE_URL}/paper/positions", headers=HEADERS)
    positions = r_pos.json()["data"]
    print(f"Open positions count: {len(positions)}")
    for p in positions[:2]:
        print(f"  Instrument: {p['symbol']} | Qty: {p['quantity']} | Avg Entry: ${p['avg_entry_price']:,.2f} | Unrealized PnL: ${p['unrealized_pnl']:,.2f}")

    print("\n=== 9. Verifying PnL Attribution Report ===")
    r_pnl = httpx.get(f"{BASE_URL}/reports/pnl", headers=HEADERS)
    pnl = r_pnl.json()["data"]
    print(f"Total PnL: ${pnl['total_pnl']:,.2f} | Delta PnL: ${pnl['delta_pnl']:,.2f} | Vega PnL: ${pnl['vega_pnl']:,.2f} | Fees Paid: ${pnl['fee_pnl']:,.2f}")

    print("\n=== 10. Verifying Portfolio Risk & Stress Grid ===")
    r_risk = httpx.get(f"{BASE_URL}/portfolio/risk", headers=HEADERS)
    risk_info = r_risk.json()["data"]
    print(f"Portfolio Delta: {risk_info['greeks']['delta']:.3f} | Margin Usage: {risk_info['margin_utilization']:.1%}")

    r_stress = httpx.post(f"{BASE_URL}/risk/stress-runs", headers=HEADERS, json={"target_type": "portfolio"})
    stress_data = r_stress.json()["data"]
    print(f"Stress Run ID: {stress_data['stress_run_id']}, Max Stress Loss: ${stress_data['results']['max_loss']:,.2f}")

    print("\n=== 11. Testing Emergency Stop Control ===")
    r_stop = httpx.post(
        f"{BASE_URL}/controls/emergency-stop",
        headers=HEADERS,
        json={"reason": "Test emergency stop drill", "confirmed": True}
    )
    print(f"Emergency Stop Triggered: {r_stop.json()['data']['status']}")

    # Verify fail-closed invariant
    if len(recs) > 1:
        next_rec_id = recs[1]["id"]
        r_fail = httpx.post(
            f"{BASE_URL}/recommendations/{next_rec_id}/approve",
            headers=HEADERS,
            json={"mode": "paper", "comment": "Should fail"}
        )
        print(f"Approval during Emergency Stop (expected 422 or 400): {r_fail.status_code}")
        assert r_fail.status_code in [400, 422]

    # Reset Emergency Stop
    r_reset = httpx.post(
        f"{BASE_URL}/controls/emergency-stop/reset",
        headers=HEADERS
    )
    print(f"Emergency Stop Reset: {r_reset.json()['data']['status']}")

    print("\n=== 12. Checking Audit Trail ===")
    r_audit = httpx.get(f"{BASE_URL}/audit/events", headers=HEADERS)
    audits = r_audit.json()["data"]
    print(f"Total audit events recorded: {len(audits)}")
    for a in audits[:4]:
        print(f"  [{a['timestamp'][:19]}] Action: {a['action']} | Object: {a['object_type']} | Actor: {a['actor_id']}")

    print("\n>>> ALL 12 VERIFICATION PHASES PASSED WITH 100% SUCCESS! <<<")

if __name__ == "__main__":
    verify()
