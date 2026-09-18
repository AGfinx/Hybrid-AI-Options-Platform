"use client";

import React from "react";
import { TrendingUp, Layers, CheckCircle2, Clock, ShieldCheck, RefreshCw } from "lucide-react";

interface PaperTradingViewProps {
  orders: any[];
  positions: any[];
  pnlReport: any;
  onRefresh: () => void;
}

export default function PaperTradingView({
  orders,
  positions,
  pnlReport,
  onRefresh,
}: PaperTradingViewProps) {
  const activePositions = positions || [];
  const paperOrders = orders || [];
  const totalPnl = pnlReport?.total_pnl || 0;

  return (
    <div className="space-y-6">
      {/* Overview Stats */}
      <div className="glass-panel p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-100">Deterministic Paper Trading Simulator</h2>
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-800 uppercase">
              Paper Fill Engine Active
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Simulates market & limit order execution with bid/ask spread crossing, fee schedules (3 bps), slippage models, and automated delta hedging.
          </p>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right text-xs font-mono-num">
            <span className="text-slate-400 block">Total Simulated P&L</span>
            <span className={`text-base font-bold ${totalPnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {totalPnl >= 0 ? `+$${totalPnl.toFixed(2)}` : `-$${Math.abs(totalPnl).toFixed(2)}`}
            </span>
          </div>

          <button
            onClick={onRefresh}
            className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs border border-slate-700 transition flex items-center gap-1.5"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Refresh Ledger</span>
          </button>
        </div>
      </div>

      {/* Active Positions Table */}
      <div className="glass-panel p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h3 className="font-bold text-slate-100 text-base">Current Portfolio Positions</h3>
            <p className="text-xs text-slate-400">Live mark-to-market positions and real-time Greek sensitivities</p>
          </div>
          <span className="text-xs font-mono-num text-cyan-400 bg-cyan-950 border border-cyan-800 px-2.5 py-0.5 rounded">
            {activePositions.length} Open Positions
          </span>
        </div>

        {activePositions.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-sm">
            No open paper positions. Approve pending recommendations to generate paper fills.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left font-mono-num">
              <thead className="bg-slate-900 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Instrument</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Strike ($)</th>
                  <th className="py-2.5 px-3">Qty</th>
                  <th className="py-2.5 px-3">Entry Price ($)</th>
                  <th className="py-2.5 px-3">Mark Price ($)</th>
                  <th className="py-2.5 px-3">Delta</th>
                  <th className="py-2.5 px-3">Vega</th>
                  <th className="py-2.5 px-3">Unrealized P&L</th>
                  <th className="py-2.5 px-3 text-right">Realized P&L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-200">
                {activePositions.map((p) => {
                  const unrl = p.unrealized_pnl || 0;
                  const rl = p.realized_pnl || 0;
                  return (
                    <tr key={p.id} className="hover:bg-slate-800/40 transition">
                      <td className="py-2.5 px-3 font-bold text-slate-100">{p.symbol}</td>
                      <td className="py-2.5 px-3 uppercase text-[11px] font-bold">
                        <span className={p.option_type === "call" ? "text-emerald-400" : "text-purple-400"}>
                          {p.option_type}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">${p.strike?.toLocaleString()}</td>
                      <td className="py-2.5 px-3 font-semibold text-cyan-400">
                        {p.quantity > 0 ? `+${p.quantity}` : p.quantity}
                      </td>
                      <td className="py-2.5 px-3">${p.avg_entry_price?.toLocaleString()}</td>
                      <td className="py-2.5 px-3">${p.current_mark_price?.toLocaleString()}</td>
                      <td className="py-2.5 px-3 text-slate-400">{p.delta > 0 ? `+${p.delta}` : p.delta}</td>
                      <td className="py-2.5 px-3 text-slate-400">${p.vega}</td>
                      <td className={`py-2.5 px-3 font-bold ${unrl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {unrl >= 0 ? `+$${unrl.toFixed(2)}` : `-$${Math.abs(unrl).toFixed(2)}`}
                      </td>
                      <td className={`py-2.5 px-3 text-right font-bold ${rl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {rl >= 0 ? `+$${rl.toFixed(2)}` : `-$${Math.abs(rl).toFixed(2)}`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Paper Order History */}
      <div className="glass-panel p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h3 className="font-bold text-slate-100 text-base">Paper Order Execution History</h3>
            <p className="text-xs text-slate-400">Deterministic order execution log with slippage and fee tracking</p>
          </div>
          <span className="text-xs font-mono-num text-slate-400">
            {paperOrders.length} Executed Orders
          </span>
        </div>

        {paperOrders.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-sm">
            No paper orders have been placed yet.
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[360px] overflow-y-auto">
            <table className="w-full text-xs text-left font-mono-num">
              <thead className="sticky top-0 bg-slate-900 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Order ID</th>
                  <th className="py-2.5 px-3">Symbol</th>
                  <th className="py-2.5 px-3">Side</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Quantity</th>
                  <th className="py-2.5 px-3">Fill Price</th>
                  <th className="py-2.5 px-3">Fee Paid</th>
                  <th className="py-2.5 px-3">Slippage</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-200">
                {paperOrders.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-800/40 transition">
                    <td className="py-2 px-3 text-slate-400">{o.id}</td>
                    <td className="py-2 px-3 font-semibold text-slate-100">{o.symbol}</td>
                    <td className="py-2 px-3 uppercase font-bold text-[11px]">
                      <span className={o.direction === "buy" ? "text-emerald-400" : "text-purple-400"}>
                        {o.direction}
                      </span>
                    </td>
                    <td className="py-2 px-3 uppercase text-[11px] text-slate-400">{o.order_type}</td>
                    <td className="py-2 px-3">{o.quantity}</td>
                    <td className="py-2 px-3 font-semibold text-cyan-400">${o.avg_fill_price || "—"}</td>
                    <td className="py-2 px-3 text-rose-400">${o.fee_assumed || 0}</td>
                    <td className="py-2 px-3 text-rose-400">${o.slippage_assumed || 0}</td>
                    <td className="py-2 px-3">
                      <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">
                        {o.status}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right text-slate-400">
                      {new Date(o.created_at).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
