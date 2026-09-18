import datetime
import json
from db.database import SessionLocal, init_db
from db.models import (
    Venue, Instrument, InstrumentVersion, Permission, Role, User,
    RiskLimit, CircuitBreaker, ModelVersion, Mandate
)

def seed_database():
    init_db()
    db = SessionLocal()

    try:
        # 1. Venue
        venue = db.query(Venue).filter_by(id="deribit").first()
        if not venue:
            venue = Venue(
                id="deribit",
                name="Deribit Cryptocurrency Derivatives",
                venue_type="deribit",
                is_active=True
            )
            db.add(venue)

        # 2. Permissions
        perm_defs = [
            ("read:market", "Read market data and volatility surfaces"),
            ("read:recommendations", "Read volatility trade recommendations"),
            ("approve:recommendations", "Approve recommendations for paper trading"),
            ("edit:recommendations", "Edit recommendation parameters"),
            ("execute:paper", "Submit and manage paper trading orders"),
            ("manage:risk", "Configure and inspect risk limits"),
            ("manage:mandate", "Create, pause, and terminate strategy mandates"),
            ("emergency:stop", "Trigger emergency stop circuit breaker"),
        ]
        perms = {}
        for p_id, p_desc in perm_defs:
            perm = db.query(Permission).filter_by(id=p_id).first()
            if not perm:
                perm = Permission(id=p_id, name=p_id, description=p_desc)
                db.add(perm)
            perms[p_id] = perm

        # 3. Roles
        admin_role = db.query(Role).filter_by(id="admin").first()
        if not admin_role:
            admin_role = Role(
                id="admin",
                name="Administrator",
                description="Superuser with full authority across all modules"
            )
            admin_role.permissions = list(perms.values())
            db.add(admin_role)

        trader_role = db.query(Role).filter_by(id="trader").first()
        if not trader_role:
            trader_role = Role(
                id="trader",
                name="Quantitative Trader",
                description="Trader role with recommendation approval and paper execution rights"
            )
            trader_role.permissions = [
                perms["read:market"], perms["read:recommendations"],
                perms["approve:recommendations"], perms["edit:recommendations"],
                perms["execute:paper"]
            ]
            db.add(trader_role)

        # 4. User
        dev_user = db.query(User).filter_by(id="user_dev_01").first()
        if not dev_user:
            dev_user = User(
                id="user_dev_01",
                username="quant_lead",
                email="lead@optionsplatform.local",
                hashed_token="dev-token",
                is_active="active"
            )
            dev_user.roles = [admin_role]
            db.add(dev_user)

        # 5. Model Versions
        models = [
            ("surface_bilinear_v1", "surface_bilinear", "1.0.0", "Bilinear smile & term-structure interpolation baseline"),
            ("surface_svi_v1", "surface_svi", "1.0.0", "Jim Gatheral SVI (Stochastic Volatility Inspired) parametric smile model"),
            ("rv_forecaster_v1", "rv_ridge", "1.0.0", "Time-aware Ridge realized volatility forecaster with uncertainty bounds"),
        ]
        for m_id, name, ver, desc in models:
            mv = db.query(ModelVersion).filter_by(id=m_id).first()
            if not mv:
                mv = ModelVersion(
                    id=m_id,
                    model_name=name,
                    version=ver,
                    description=desc,
                    parameters_json=json.dumps({"features": ["rolling_7d", "rolling_14d", "rolling_30d"]}),
                    is_active=True
                )
                db.add(mv)

        # 6. Risk Limits
        limits = [
            ("max_delta", "portfolio", 5.0, 3.5),
            ("max_gamma", "portfolio", 0.05, 0.035),
            ("max_vega", "portfolio", 50000.0, 35000.0),
            ("max_theta", "portfolio", 10000.0, 7500.0),
            ("max_loss", "portfolio", 50000.0, 35000.0),
            ("margin_utilization", "portfolio", 0.70, 0.50),
            ("max_drawdown", "portfolio", 0.15, 0.10),
            ("max_quote_age_seconds", "market", 15.0, 10.0),
            ("max_var_99_1d", "portfolio", 35000.0, 25000.0),
        ]
        for lname, scope, val, warn in limits:
            rl = db.query(RiskLimit).filter_by(limit_name=lname, scope=scope).first()
            if not rl:
                rl = RiskLimit(
                    id=f"rl_{scope}_{lname}",
                    scope=scope,
                    limit_name=lname,
                    limit_value=val,
                    warning_threshold=warn,
                    is_active=True
                )
                db.add(rl)

        # 7. Circuit Breakers
        breakers = [
            ("emergency_stop", "Manual emergency stop operator trigger"),
            ("max_drawdown_breaker", "Portfolio drawdown exceeds 15%"),
            ("stale_market_data_breaker", "Quote age exceeds 30 seconds"),
        ]
        for b_name, cond in breakers:
            cb = db.query(CircuitBreaker).filter_by(name=b_name).first()
            if not cb:
                cb = CircuitBreaker(
                    id=f"cb_{b_name}",
                    name=b_name,
                    trigger_condition=cond,
                    is_tripped=False
                )
                db.add(cb)

        # 8. Mandates (BTC and ETH)
        mandate_btc = db.query(Mandate).filter_by(id="mandate_btc_vol_01").first()
        if not mandate_btc:
            mandate_btc = Mandate(
                id="mandate_btc_vol_01",
                strategy="btc_volatility_arbitrage",
                allowed_instruments_json=json.dumps(["BTC-*"]),
                venues_json=json.dumps(["deribit"]),
                mode="recommendation",
                capital_limit=500000.0,
                max_drawdown_limit=0.15,
                max_delta_limit=5.0,
                max_vega_limit=50000.0,
                max_var_limit=100000.0,
                hedge_permissions="within_mandate",
                is_active=True,
                status="active",
                expiry_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=90)
            )
            db.add(mandate_btc)

        mandate_eth = db.query(Mandate).filter_by(id="mandate_eth_vol_01").first()
        if not mandate_eth:
            mandate_eth = Mandate(
                id="mandate_eth_vol_01",
                strategy="eth_volatility_arbitrage",
                allowed_instruments_json=json.dumps(["ETH-*"]),
                venues_json=json.dumps(["deribit"]),
                mode="recommendation",
                capital_limit=250000.0,
                max_drawdown_limit=0.15,
                max_delta_limit=25.0,
                max_vega_limit=30000.0,
                max_var_limit=50000.0,
                hedge_permissions="within_mandate",
                is_active=True,
                status="active",
                expiry_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=90)
            )
            db.add(mandate_eth)

        # 9. Synthetic BTC & ETH Instruments
        now = datetime.datetime.now(datetime.timezone.utc)
        expiry_days = [7, 14, 30, 60]

        assets = [
            ("BTC", 65000.0, [55000.0, 60000.0, 62500.0, 65000.0, 67500.0, 70000.0, 75000.0], 0.5),
            ("ETH", 3500.0, [2800.0, 3000.0, 3200.0, 3500.0, 3800.0, 4000.0, 4200.0], 0.1),
        ]

        for underlying, spot_ref, strikes, tick_sz in assets:
            for d in expiry_days:
                exp_date = (now + datetime.timedelta(days=d)).replace(hour=8, minute=0, second=0, microsecond=0)
                exp_str = exp_date.strftime("%d%b%y").upper()

                for s in strikes:
                    for opt_type in ["call", "put"]:
                        s_int = int(s)
                        flag = "C" if opt_type == "call" else "P"
                        symbol = f"{underlying}-{exp_str}-{s_int}-{flag}"

                        existing = db.query(Instrument).filter_by(symbol=symbol).first()
                        if not existing:
                            inst = Instrument(
                                id=f"inst_{symbol.lower()}",
                                venue_id="deribit",
                                symbol=symbol,
                                underlying=underlying,
                                option_type=opt_type,
                                strike=s,
                                expiry=exp_date,
                                currency="USD",
                                tick_size=tick_sz,
                                contract_size=1.0,
                                is_active=True
                            )
                            db.add(inst)

                            ver = InstrumentVersion(
                                id=f"ver_{symbol.lower()}_1",
                                instrument_id=inst.id,
                                version=1,
                                parameters_json=json.dumps({"initial_spot": spot_ref})
                            )
                            db.add(ver)

        db.commit()
        print("Database seeded successfully with all 24 core domain entities (BTC & ETH universes).")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
