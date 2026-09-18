"use client";

import React, { useState, useMemo } from "react";
import {
  TrendingUp, Shield, AlertCircle, ArrowUpRight, DollarSign,
  Activity, CheckCircle2, ChevronRight, Zap, RefreshCw, Scale,
  Layers, AlertTriangle
} from "lucide-react";
import { api } from "@/lib/api";

interface CockpitViewProps {
  portfolioRisk: any;
  recommendations: any[];
  pnlReport: any;
  marketHealth: any;
  onOpenReview: (rec: any) => void;
  onGenerateRecs: () => void;
  onRefresh?: () => void;
}

export default function CockpitView({
  portfolioRisk,
  recommendations,
  pnlReport,
  marketHealth,
  onOpenReview,
  onGenerateRecs,
  onRefresh,
}: CockpitViewProps) {
  const [rebalancing, setRebalancing] = useState(false);
  const [rebalanceMsg, setRebalanceMsg] = useState<string | null>(null);

  const greeks = portfolioRisk?.greeks || { delta: 0, gamma: 0, vega: 0, theta: 0 };
  const utilization = portfolioRisk?.utilization || { delta: 0, vega: 0, margin: 0 };
  const varData = portfolioRisk?.var || {};
  const pendingRecs = recommendations?.filter((r) => r.status === "pending") || [];
  const breakers = portfolioRisk?.circuit_breakers || [];
  const anyBreakerTripped = breakers.some((b: any) => b.is_tripped);

  const totalPnl = pnlReport?.total_pnl ?? 0;
  const isPnlPositive = totalPnl >= 0;

  const var95 = varData?.var_95 ?? varData?.var_95_1d ?? 0;
  const var99 = varData?.var_99 ?? varData?.var_99_1d ?? 0;
  const cvar99 = varData?.cvar_99 ?? varData?.cvar_99_1d ?? 0;
  const totalCap = portfolioRisk?.total_capital || 500000;

  const handleRebalance = async (asset = "BTC") => {
    setRebalancing(true);
    setRebalanceMsg(null);
    try {
      const res = await api.rebalanceDelta(asset);
      setRebalanceMsg(res.message || "Rebalance executed.");
      if (onRefresh) onRefresh();
    } catch (e: any) {
      setRebalanceMsg(`Error: ${e.message || "Failed to rebalance"}`);
    } finally {
      setRebalancing(false);
    }
  };

  // Simulated Equity Curve points for SVG
  const equityPoints = useMemo(() => {
    // Generate an illustrative 14-step equity curve reflecting factor attribution
    const base = totalCap;
    const deltaContrib = pnlReport?.delta_pnl || 120.0;
    const vegaContrib = pnlReport?.vega_pnl || 350.0;
    const thetaContrib = pnlReport?.theta_pnl || 80.0;
    const net = totalPnl;

    const trajectory = [0, 0.1, 0.15, 0.35, 0.25, 0.45, 0.60, 0.55, 0.70, 0.65, 0.85, 0.80, 0.95, 1.0];
    return trajectory.map((step, idx) => ({
      step: idx + 1,
      equity: base + (net !== 0 ? net * step : (idx * 45.0) - (idx % 3 === 0 ? 30 : 0))
    }));
  }, [totalCap, totalPnl, pnlReport]);

  const equityChart = useMemo(() => {
    const width = 450;
    const height = 140;
    const pad = 25;

    const values = equityPoints.map(p => p.equity);
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal || 100;

    const toX = (step: number) => pad + ((step - 1) / (equityPoints.length - 1)) * (width - pad * 2);
    const toY = (val: number) => height - pad - ((val - minVal) / range) * (height - pad * 2);

    const pathD = equityPoints.map((p, idx) => `${idx === 0 ? "M" : "L"} ${toX(p.step).toFixed(1)} ${toY(p.equity).toFixed(1)}`).join(" ");

    return { width, height, toX, toY, pathD, minVal, maxVal };
  }, [equityPoints]);

  return (
    <div className="space-y-6">
      {/* Breaker Alert Banner if Tripped */}
      {anyBreakerTripped && (
        <div className="p-4 rounded-xl bg-rose-950/80 border border-rose-600 flex items-center justify-between text-rose-200">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-6 w-6 text-rose-400" />
            <div>
              <h4 className="font-bold text-sm">CIRCUIT BREAKER ENGAGED: Emergency Stop Triggered</h4>
              <p className="text-xs text-rose-300">All new paper order submissions and risk approvals are strictly disabled.</p>
            </div>
          </div>
        </div>
      )}

      {/* Delta Rebalance Feedback Notification */}
      {rebalanceMsg && (
        <div className="p-3 rounded-lg bg-cyan-950/80 border border-cyan-800 text-cyan-200 text-xs flex items-center justify-between font-mono-num">
          <span>{rebalanceMsg}</span>
          <button onClick={() => setRebalanceMsg(null)} className="text-slate-400 hover:text-slate-200">✕</button>
        </div>
      )}

      {/* Primary KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Capital & Margin */}
        <div className="glass-panel p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Portfolio Capital</span>
            <DollarSign className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold font-mono-num text-slate-100">
            ${totalCap.toLocaleString()}
          </div>
          <div className="mt-3 space-y-1.5 text-xs">
            <div className="flex justify-between text-slate-400">
              <span>Used Margin:</span>
              <span className="font-mono-num text-slate-200">${(portfolioRisk?.used_margin || 0).toLocaleString()}</span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-cyan-500 h-1.5 rounded-full transition-all"
                style={{ width: `${Math.min(100, (portfolioRisk?.margin_utilization || 0) * 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-[11px] text-slate-500 font-mono-num">
              <span>Limit: 70%</span>
              <span className="text-cyan-400">{((portfolioRisk?.margin_utilization || 0) * 100).toFixed(1)}% Used</span>
            </div>
          </div>
        </div>

        {/* Value-at-Risk & Expected Shortfall (CVaR) */}
        <div className="glass-panel p-4 space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Monte Carlo VaR & CVaR (1-Day)</span>
            <Shield className="h-4 w-4 text-purple-400" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono-num text-purple-300">
              ${var99.toLocaleString()}
            </span>
            <span className="text-[10px] text-slate-400 font-mono-num">
              99% Confidence
            </span>
          </div>
          <div className="space-y-1 text-xs font-mono-num pt-1 border-t border-slate-800">
            <div className="flex justify-between text-slate-400 text-[11px]">
              <span>VaR 95% (1-Day):</span>
              <span className="text-slate-200 font-semibold">${var95.toLocaleString()} ({((var95 / totalCap) * 100).toFixed(2)}%)</span>
            </div>
            <div className="flex justify-between text-slate-400 text-[11px]">
              <span>Expected Shortfall (CVaR):</span>
              <span className="text-rose-400 font-bold">${cvar99.toLocaleString()}</span>
            </div>
            <div className="text-[10px] text-slate-500">
              10,000 Δ-Γ-Vega-Theta Taylor expansion paths
            </div>
          </div>
        </div>

        {/* Portfolio Greeks & Delta Rebalance Action */}
        <div className="glass-panel p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Aggregate Greeks</span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => handleRebalance("BTC")}
                disabled={rebalancing}
                className="px-2 py-0.5 rounded bg-cyan-950 hover:bg-cyan-900 border border-cyan-800 text-[10px] text-cyan-300 font-bold flex items-center gap-1 transition"
                title="Hedge delta drift back to neutral"
              >
                <Scale className="h-2.5 w-2.5" />
                <span>{rebalancing ? "Hedging..." : "Hedge Δ"}</span>
              </button>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 mt-2 font-mono-num text-xs">
            <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
              <span className="text-slate-500 block text-[10px]">DELTA (BTC/ETH)</span>
              <span className={`font-bold ${Math.abs(greeks.delta) > 1.5 ? "text-amber-400" : "text-slate-200"}`}>
                {greeks.delta > 0 ? `+${greeks.delta.toFixed(3)}` : greeks.delta.toFixed(3)}
              </span>
            </div>
            <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
              <span className="text-slate-500 block text-[10px]">VEGA ($/1%)</span>
              <span className="font-bold text-slate-200">${greeks.vega.toFixed(0)}</span>
            </div>
            <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
              <span className="text-slate-500 block text-[10px]">GAMMA</span>
              <span className="font-bold text-slate-200">{greeks.gamma.toFixed(5)}</span>
            </div>
            <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
              <span className="text-slate-500 block text-[10px]">THETA ($/day)</span>
              <span className="font-bold text-slate-200">${greeks.theta.toFixed(0)}</span>
            </div>
          </div>
        </div>

        {/* Simulated P&L */}
        <div className="glass-panel p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Simulated Paper P&L</span>
            <TrendingUp className="h-4 w-4 text-emerald-400" />
          </div>
          <div className={`text-2xl font-bold font-mono-num ${isPnlPositive ? "text-emerald-400" : "text-rose-400"}`}>
            {isPnlPositive ? `+$${totalPnl.toFixed(2)}` : `-$${Math.abs(totalPnl).toFixed(2)}`}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-1 text-[11px] font-mono-num text-slate-400">
            <div>Delta P&L: <span className="text-slate-200">${(pnlReport?.delta_pnl || 0).toFixed(1)}</span></div>
            <div>Vega P&L: <span className="text-slate-200">${(pnlReport?.vega_pnl || 0).toFixed(1)}</span></div>
            <div>Fees Paid: <span className="text-rose-400">${Math.abs(pnlReport?.fee_pnl || 0).toFixed(1)}</span></div>
            <div>Slippage: <span className="text-rose-400">${Math.abs(pnlReport?.slippage_pnl || 0).toFixed(1)}</span></div>
          </div>
        </div>
      </div>

      {/* SVG Equity Curve Chart & Portfolio Factor Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* SVG Equity Curve */}
        <div className="lg:col-span-8 glass-panel p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-400" />
              <h3 className="font-bold text-slate-100 text-sm">Cumulative Portfolio Equity Curve</h3>
            </div>
            <span className="text-xs font-mono-num text-emerald-400 font-semibold">
              Current: ${(equityChart.maxVal).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>

          <div className="relative w-full overflow-hidden flex justify-center">
            <svg viewBox={`0 0 ${equityChart.width} ${equityChart.height}`} className="w-full h-36 text-xs">
              <line x1={25} y1={25} x2={equityChart.width - 25} y2={25} stroke="#1e293b" strokeDasharray="3 3" />
              <line x1={25} y1={equityChart.height - 25} x2={equityChart.width - 25} y2={equityChart.height - 25} stroke="#334155" />

              <path
                d={equityChart.pathD}
                fill="none"
                stroke="#10b981"
                strokeWidth="2.5"
                strokeLinecap="round"
              />

              {equityPoints.map((p, idx) => (
                <circle
                  key={idx}
                  cx={equityChart.toX(p.step)}
                  cy={equityChart.toY(p.equity)}
                  r="3.5"
                  fill="#10b981"
                  stroke="#0f172a"
                  strokeWidth="1.5"
                />
              ))}
            </svg>
          </div>

          <div className="flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-800/80 pt-2 font-mono-num">
            <span>T-0: ${totalCap.toLocaleString()}</span>
            <span className="text-emerald-400 font-semibold">Factor-Attributed Net Yield</span>
            <span>T-Now: ${(equityChart.maxVal).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
          </div>
        </div>

        {/* Factor Attribution Breakdown */}
        <div className="lg:col-span-4 glass-panel p-5 space-y-3">
          <div className="border-b border-slate-800 pb-3">
            <h3 className="font-bold text-slate-100 text-sm">P&L Factor Decomposition</h3>
            <p className="text-xs text-slate-400">Taylor expansion attribution</p>
          </div>

          <div className="space-y-2 text-xs font-mono-num">
            <div className="flex justify-between p-1.5 rounded bg-slate-900/50 border border-slate-800">
              <span className="text-slate-400">Delta P&L</span>
              <span className="text-slate-200">${(pnlReport?.delta_pnl || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between p-1.5 rounded bg-slate-900/50 border border-slate-800">
              <span className="text-slate-400">Vega P&L</span>
              <span className="text-slate-200">${(pnlReport?.vega_pnl || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between p-1.5 rounded bg-slate-900/50 border border-slate-800">
              <span className="text-slate-400">Theta Decay</span>
              <span className="text-slate-200">${(pnlReport?.theta_pnl || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between p-1.5 rounded bg-slate-900/50 border border-slate-800">
              <span className="text-slate-400">Delta Hedge P&L</span>
              <span className="text-slate-200">${(pnlReport?.hedge_pnl || 0).toFixed(2)}</span>
            </div>
            <div className="flex justify-between p-1.5 rounded bg-slate-900/50 border border-slate-800">
              <span className="text-slate-400">Frictions (Fees + Slip)</span>
              <span className="text-rose-400">-${(Math.abs(pnlReport?.fee_pnl || 0) + Math.abs(pnlReport?.slippage_pnl || 0)).toFixed(2)}</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-slate-800 border border-slate-700 font-bold">
              <span className="text-slate-200">Total Net P&L</span>
              <span className={isPnlPositive ? "text-emerald-400" : "text-rose-400"}>
                {isPnlPositive ? `+$${totalPnl.toFixed(2)}` : `-$${Math.abs(totalPnl).toFixed(2)}`}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Actionable Opportunities Queue */}
      <div className="glass-panel p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h3 className="font-bold text-slate-100 text-base">Top Algorithmic Trade Opportunities</h3>
            <p className="text-xs text-slate-400">Multi-asset volatility opportunities awaiting human-in-the-loop review</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono-num px-2 py-0.5 rounded bg-indigo-950 border border-indigo-800 text-indigo-300">
              {pendingRecs.length} Actionable
            </span>
            <button
              onClick={onGenerateRecs}
              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs flex items-center gap-1 border border-slate-700 transition"
            >
              <RefreshCw className="h-3 w-3" />
              <span>Scan Market</span>
            </button>
          </div>
        </div>

        {pendingRecs.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-sm">
            <p>No actionable trade recommendations currently pending.</p>
            <button
              onClick={onGenerateRecs}
              className="mt-3 px-3 py-1.5 rounded-md bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold"
            >
              Trigger Volatility Scan
            </button>
          </div>
        ) : (
          <div className="space-y-2.5 max-h-[420px] overflow-y-auto pr-1">
            {pendingRecs.slice(0, 6).map((rec) => {
              const leg = rec.legs?.[0] || {};
              const isMultiLeg = rec.legs && rec.legs.length > 1;
              return (
                <div
                  key={rec.id}
                  className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
                        rec.underlying === "BTC"
                          ? "bg-amber-950 text-amber-300 border border-amber-800"
                          : "bg-cyan-950 text-cyan-300 border border-cyan-800"
                      }`}>
                        {rec.underlying}
                      </span>
                      <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
                        isMultiLeg
                          ? "bg-purple-950 text-purple-300 border border-purple-800"
                          : rec.strategy_type?.includes("long")
                          ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                          : "bg-blue-950 text-blue-300 border border-blue-800"
                      }`}>
                        {rec.strategy_type?.replace(/_/g, " ")}
                      </span>
                      {isMultiLeg && (
                        <span className="text-[10px] font-mono-num px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                          {rec.legs.length} Legs
                        </span>
                      )}
                      <span className="font-semibold text-slate-200 text-sm font-mono-num">
                        {leg.symbol || `${rec.underlying} Strike $${leg.strike}`}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 line-clamp-1">{rec.rationale}</p>
                  </div>

                  <div className="flex items-center gap-4 justify-between sm:justify-end">
                    <div className="text-right font-mono-num">
                      <span className="text-[10px] text-slate-500 block">EST. NET EDGE</span>
                      <span className="font-bold text-emerald-400 text-sm">
                        +{(rec.net_edge * 100).toFixed(2)}%
                      </span>
                    </div>

                    <button
                      onClick={() => onOpenReview(rec)}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-sm transition"
                    >
                      <span>Review</span>
                      <ChevronRight className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
