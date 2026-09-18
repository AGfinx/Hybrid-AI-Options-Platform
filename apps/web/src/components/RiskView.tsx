"use client";

import React, { useState } from "react";
import { Shield, AlertTriangle, RefreshCw, CheckCircle2, ShieldAlert, Activity } from "lucide-react";
import { api } from "@/lib/api";

interface RiskViewProps {
  portfolioRisk: any;
  onRefresh: () => void;
  onEmergencyStop: () => void;
  onResetEmergencyStop: () => void;
}

export default function RiskView({
  portfolioRisk,
  onRefresh,
  onEmergencyStop,
  onResetEmergencyStop,
}: RiskViewProps) {
  const [stressData, setStressData] = useState<any>(portfolioRisk?.stress || null);
  const [runningStress, setRunningStress] = useState<boolean>(false);

  const handleRunStress = async () => {
    setRunningStress(true);
    try {
      const res = await api.runStressTest("portfolio");
      setStressData(res.results);
    } catch (e) {
      console.error("Stress test failed:", e);
    } finally {
      setRunningStress(false);
    }
  };

  const breakers = portfolioRisk?.circuit_breakers || [];
  const greeks = portfolioRisk?.greeks || { delta: 0, gamma: 0, vega: 0, theta: 0 };
  const util = portfolioRisk?.utilization || { delta: 0, vega: 0, margin: 0 };

  const spotShocks = stressData?.spot_shocks || [-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20];
  const volShocks = stressData?.vol_shocks || [-0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15];
  const grid = stressData?.scenario_grid || [];

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="glass-panel p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-100">Independent Risk & Stress Engine</h2>
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-indigo-950 text-indigo-300 border border-indigo-800 uppercase">
              Isolated Gatekeeper Active
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Enforces hard constraints on capital, margin, portfolio Greeks, and non-linear stress scenario matrices.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRunStress}
            disabled={runningStress}
            className="px-3.5 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition flex items-center gap-1.5"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${runningStress ? "animate-spin" : ""}`} />
            <span>Re-compute Stress Grid</span>
          </button>
        </div>
      </div>

      {/* Risk Limits & Circuit Breakers Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Risk Limit Utilization Gauges */}
        <div className="lg:col-span-2 glass-panel p-5 space-y-4">
          <div className="border-b border-slate-800 pb-3">
            <h3 className="font-bold text-slate-100 text-sm">Portfolio Limit Utilization</h3>
            <p className="text-xs text-slate-400">Current exposure vs. hard policy thresholds</p>
          </div>

          <div className="space-y-4 font-mono-num text-xs">
            {/* Delta Limit */}
            <div className="space-y-1">
              <div className="flex justify-between text-slate-300">
                <span>Delta Exposure (±5.0 BTC Limit):</span>
                <span className="font-bold text-slate-100">
                  {greeks.delta > 0 ? `+${greeks.delta.toFixed(3)}` : greeks.delta.toFixed(3)} BTC ({(util.delta * 100).toFixed(1)}%)
                </span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div
                  className={`h-2 rounded-full transition-all ${util.delta > 0.8 ? "bg-rose-500" : util.delta > 0.5 ? "bg-amber-400" : "bg-cyan-500"}`}
                  style={{ width: `${Math.min(100, util.delta * 100)}%` }}
                />
              </div>
            </div>

            {/* Vega Limit */}
            <div className="space-y-1">
              <div className="flex justify-between text-slate-300">
                <span>Vega Exposure ($50,000 Limit):</span>
                <span className="font-bold text-slate-100">
                  ${greeks.vega.toFixed(0)} ({(util.vega * 100).toFixed(1)}%)
                </span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div
                  className={`h-2 rounded-full transition-all ${util.vega > 0.8 ? "bg-rose-500" : "bg-indigo-500"}`}
                  style={{ width: `${Math.min(100, util.vega * 100)}%` }}
                />
              </div>
            </div>

            {/* Margin Utilization */}
            <div className="space-y-1">
              <div className="flex justify-between text-slate-300">
                <span>Margin Utilization (70% Max Limit):</span>
                <span className="font-bold text-slate-100">
                  ${(portfolioRisk?.used_margin || 0).toLocaleString()} ({(util.margin * 100).toFixed(1)}%)
                </span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div
                  className={`h-2 rounded-full transition-all ${util.margin > 0.7 ? "bg-rose-500" : "bg-emerald-500"}`}
                  style={{ width: `${Math.min(100, util.margin * 100)}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Circuit Breakers & Emergency Controls */}
        <div className="glass-panel p-5 space-y-4">
          <div className="border-b border-slate-800 pb-3">
            <h3 className="font-bold text-slate-100 text-sm">System Circuit Breakers</h3>
            <p className="text-xs text-slate-400">Fail-closed safety locks</p>
          </div>

          <div className="space-y-3 text-xs">
            {breakers.map((cb: any) => (
              <div
                key={cb.name}
                className={`p-3 rounded-lg border flex items-center justify-between ${
                  cb.is_tripped
                    ? "bg-rose-950/70 border-rose-700 text-rose-200"
                    : "bg-slate-900/60 border-slate-800 text-slate-300"
                }`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 rounded-full ${cb.is_tripped ? "bg-rose-400 animate-ping" : "bg-emerald-400"}`} />
                    <span className="font-bold capitalize">{cb.name.replace(/_/g, " ")}</span>
                  </div>
                  <span className="text-[11px] text-slate-400 block mt-0.5">
                    {cb.is_tripped ? `Tripped: ${cb.reason || "Manual trip"}` : "Operational: Listening"}
                  </span>
                </div>

                <span className={`text-[10px] font-mono-num font-bold uppercase px-2 py-0.5 rounded ${
                  cb.is_tripped ? "bg-rose-900 text-rose-200" : "bg-emerald-950 text-emerald-300 border border-emerald-800"
                }`}>
                  {cb.is_tripped ? "TRIPPED" : "ARMED"}
                </span>
              </div>
            ))}

            {/* Quick emergency reset or trip */}
            <div className="pt-2 flex gap-2">
              <button
                onClick={onEmergencyStop}
                className="flex-1 py-1.5 rounded bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs shadow transition"
              >
                Trip E-Stop
              </button>
              <button
                onClick={onResetEmergencyStop}
                className="flex-1 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs border border-slate-700 transition"
              >
                Reset E-Stop
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 7x7 Spot & Vol Shock Scenario Heatmap */}
      <div className="glass-panel p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h3 className="font-bold text-slate-100 text-base">7x7 Non-Linear Stress Scenario Matrix</h3>
            <p className="text-xs text-slate-400">
              Joint Spot Shocks (-20% to +20%) × Implied Volatility Shocks (-15% to +15%)
            </p>
          </div>

          <div className="text-right font-mono-num text-xs">
            <span className="text-slate-400 block">Worst-Case Projected Loss</span>
            <span className="text-base font-bold text-rose-400">
              -${(stressData?.max_loss || 0).toLocaleString()}
            </span>
          </div>
        </div>

        {grid.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-center text-xs font-mono-num border-collapse">
              <thead>
                <tr>
                  <th className="p-2 text-slate-500 text-left">Spot \ Vol</th>
                  {volShocks.map((v: number) => (
                    <th key={v} className="p-2 text-slate-300 font-semibold">
                      {v > 0 ? `+${(v * 100).toFixed(0)}%` : `${(v * 100).toFixed(0)}%`}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {spotShocks.map((s: number, rIdx: number) => (
                  <tr key={s} className="border-t border-slate-800/80">
                    <td className="p-2 text-left font-semibold text-slate-300">
                      {s > 0 ? `+${(s * 100).toFixed(0)}%` : `${(s * 100).toFixed(0)}%`}
                    </td>
                    {grid[rIdx]?.map((val: number, cIdx: number) => {
                      const isNeg = val < 0;
                      const isZero = Math.abs(val) < 0.01;
                      return (
                        <td
                          key={cIdx}
                          className={`p-2 font-bold ${
                            isZero
                              ? "text-slate-500"
                              : isNeg
                              ? "text-rose-400 bg-rose-950/20"
                              : "text-emerald-400 bg-emerald-950/20"
                          }`}
                        >
                          {isNeg ? `-$${Math.abs(val).toLocaleString()}` : `+$${val.toLocaleString()}`}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-8 text-center text-slate-500 text-sm">
            Click "Re-compute Stress Grid" to evaluate positions under joint spot/volatility stress.
          </div>
        )}
      </div>
    </div>
  );
}
