"use client";

import React, { useState } from "react";
import {
  Zap, Filter, CheckCircle2, XCircle, Eye, AlertCircle,
  Sliders, ArrowUpRight, ChevronRight, ShieldCheck, DollarSign,
  Bookmark, Star, Layers, ArrowRightLeft
} from "lucide-react";
import { api } from "@/lib/api";

interface RecommendationsViewProps {
  recommendations: any[];
  onOpenReview: (rec: any) => void;
  onReject: (rec: any, reason: string) => void;
  onGenerateRecs: (underlying?: string) => void;
  onToggleWatchlist?: (recId: string) => void;
}

export default function RecommendationsView({
  recommendations,
  onOpenReview,
  onReject,
  onGenerateRecs,
  onToggleWatchlist,
}: RecommendationsViewProps) {
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterAsset, setFilterAsset] = useState<string>("all");
  const [filterStrategy, setFilterStrategy] = useState<string>("all");
  const [watchlistOnly, setWatchlistOnly] = useState<boolean>(false);
  const [minEdge, setMinEdge] = useState<number>(0.01);
  const [rejectModalRec, setRejectModalRec] = useState<any>(null);
  const [rejectReason, setRejectReason] = useState<string>("");
  const [localWatchlistMap, setLocalWatchlistMap] = useState<Record<string, boolean>>({});

  const handleToggleWatchlist = async (recId: string, currentVal: boolean) => {
    // Optimistic toggle
    setLocalWatchlistMap(prev => ({ ...prev, [recId]: !currentVal }));
    try {
      await api.toggleWatchlist(recId);
      if (onToggleWatchlist) onToggleWatchlist(recId);
    } catch (e) {
      console.error("Watchlist toggle failed:", e);
      // Revert
      setLocalWatchlistMap(prev => ({ ...prev, [recId]: currentVal }));
    }
  };

  const filtered = recommendations.filter((r) => {
    const isWl = localWatchlistMap[r.id] !== undefined ? localWatchlistMap[r.id] : Boolean(r.is_watchlist);
    if (watchlistOnly && !isWl) return false;
    if (filterStatus !== "all" && r.status !== filterStatus) return false;
    if (filterAsset !== "all" && r.underlying !== filterAsset) return false;
    if (filterStrategy !== "all") {
      if (filterStrategy === "straddle" && !r.strategy_type?.includes("straddle")) return false;
      if (filterStrategy === "calendar" && !r.strategy_type?.includes("calendar")) return false;
      if (filterStrategy === "single" && (r.legs && r.legs.length > 1)) return false;
    }
    if (r.net_edge < minEdge) return false;
    return true;
  });

  const handleConfirmReject = () => {
    if (!rejectModalRec || !rejectReason.trim()) return;
    onReject(rejectModalRec, rejectReason.trim());
    setRejectModalRec(null);
    setRejectReason("");
  };

  return (
    <div className="space-y-6">
      {/* Filter & Controls Header */}
      <div className="glass-panel p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-100">Trade Opportunity Queue</h2>
            <span className="text-xs font-mono-num px-2 py-0.5 rounded bg-indigo-950 border border-indigo-800 text-indigo-300">
              {filtered.length} Discovered
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Algorithmic volatility edge recommendations across single-leg, delta-neutral straddles, and calendar spreads.
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Watchlist Quick Filter */}
          <button
            onClick={() => setWatchlistOnly(!watchlistOnly)}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition border ${
              watchlistOnly
                ? "bg-amber-500/20 text-amber-300 border-amber-500/50"
                : "bg-slate-900 text-slate-400 border-slate-700 hover:text-slate-200"
            }`}
          >
            <Star className={`h-3.5 w-3.5 ${watchlistOnly ? "fill-amber-400 text-amber-400" : ""}`} />
            <span>Watchlist Only</span>
          </button>

          {/* Asset Filter */}
          <select
            value={filterAsset}
            onChange={(e) => setFilterAsset(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-200 rounded-md px-3 py-1.5 text-xs focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Assets (BTC & ETH)</option>
            <option value="BTC">BTC Only</option>
            <option value="ETH">ETH Only</option>
          </select>

          {/* Strategy Type Filter */}
          <select
            value={filterStrategy}
            onChange={(e) => setFilterStrategy(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-200 rounded-md px-3 py-1.5 text-xs focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Strategy Formats</option>
            <option value="straddle">Delta-Neutral Straddles</option>
            <option value="calendar">Term Calendar Spreads</option>
            <option value="single">Single-Leg Outrights</option>
          </select>

          {/* Status Filter */}
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-200 rounded-md px-3 py-1.5 text-xs focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Statuses</option>
            <option value="pending">Pending Review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>

          {/* Min Edge Slider */}
          <div className="flex items-center gap-2 bg-slate-900 border border-slate-700 px-3 py-1 rounded-md text-xs font-mono-num">
            <span className="text-slate-400">Min Net Edge:</span>
            <input
              type="range"
              min="0.005"
              max="0.05"
              step="0.005"
              value={minEdge}
              onChange={(e) => setMinEdge(parseFloat(e.target.value))}
              className="w-16 accent-cyan-500"
            />
            <span className="font-bold text-cyan-400">{(minEdge * 100).toFixed(1)}%</span>
          </div>

          <button
            onClick={() => onGenerateRecs()}
            className="px-3 py-1.5 rounded-md bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs transition flex items-center gap-1.5 shadow-md shadow-indigo-600/20"
          >
            <Zap className="h-3.5 w-3.5" />
            <span>Scan Market</span>
          </button>
        </div>
      </div>

      {/* Recommendations Cards Grid */}
      {filtered.length === 0 ? (
        <div className="glass-panel py-16 text-center text-slate-500 text-sm space-y-3">
          <p>No trade recommendations match the current filters or watchlist criteria.</p>
          <button
            onClick={() => onGenerateRecs()}
            className="px-4 py-2 rounded-md bg-indigo-600 text-white text-xs font-semibold"
          >
            Scan Multi-Asset Universe (BTC & ETH)
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {filtered.map((rec) => {
            const legs = rec.legs || [];
            const primaryLeg = legs[0] || {};
            const isPending = rec.status === "pending";
            const costs = rec.costs || {};
            const greeks = rec.greeks || {};
            const isMultiLeg = legs.length > 1;
            const isWl = localWatchlistMap[rec.id] !== undefined ? localWatchlistMap[rec.id] : Boolean(rec.is_watchlist);

            return (
              <div
                key={rec.id}
                className="glass-panel p-5 space-y-4 hover:border-slate-700 transition relative"
              >
                {/* Card Header */}
                <div className="flex items-start justify-between gap-2 border-b border-slate-800 pb-3">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      {/* Underlying Badge */}
                      <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
                        rec.underlying === "BTC"
                          ? "bg-amber-950 text-amber-300 border border-amber-800"
                          : "bg-cyan-950 text-cyan-300 border border-cyan-800"
                      }`}>
                        {rec.underlying}
                      </span>

                      {/* Strategy Badge */}
                      <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                        isMultiLeg
                          ? "bg-purple-950 text-purple-300 border border-purple-800"
                          : rec.strategy_type?.includes("long")
                          ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                          : "bg-blue-950 text-blue-300 border border-blue-800"
                      }`}>
                        {rec.strategy_type?.replace(/_/g, " ")}
                      </span>

                      {/* Multi-Leg indicator */}
                      {isMultiLeg && (
                        <span className="text-[10px] font-mono-num px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1">
                          <Layers className="h-2.5 w-2.5" />
                          <span>{legs.length} Legs</span>
                        </span>
                      )}

                      <span className="font-bold text-slate-100 text-sm font-mono-num">
                        {isMultiLeg
                          ? `${rec.underlying} Multi-Leg Strategy`
                          : (primaryLeg.symbol || `${rec.underlying} Strike $${primaryLeg.strike}`)}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 mt-1.5 text-[11px] text-slate-400 font-mono-num flex-wrap">
                      <span>Order Price: <strong className="text-cyan-400">${primaryLeg.order_price || rec.order_price || 0}</strong></span>
                      <span>•</span>
                      <span>Expiry: {new Date(rec.expiry_at).toLocaleTimeString()}</span>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    {/* Watchlist Toggle Star Button */}
                    <button
                      onClick={() => handleToggleWatchlist(rec.id, isWl)}
                      className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-amber-400 transition"
                      title={isWl ? "Remove from Watchlist" : "Add to Watchlist"}
                    >
                      <Star className={`h-4 w-4 ${isWl ? "fill-amber-400 text-amber-400" : ""}`} />
                    </button>

                    <div className="text-right font-mono-num">
                      <span className="text-[10px] text-slate-500 block">NET VOL EDGE</span>
                      <span className="text-base font-bold text-emerald-400">
                        +{(rec.net_edge * 100).toFixed(2)}%
                      </span>
                      <span className="text-[10px] text-slate-500 block">Gross: +{(rec.gross_edge * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                </div>

                {/* Multi-Leg Breakdown Component */}
                {isMultiLeg && (
                  <div className="space-y-1.5 font-mono-num text-xs">
                    <span className="text-[10px] uppercase font-semibold text-slate-400 flex items-center gap-1">
                      <Layers className="h-3 w-3 text-purple-400" />
                      <span>Atomic Strategy Legs</span>
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {legs.map((leg: any, lIdx: number) => (
                        <div key={lIdx} className="p-2 rounded bg-slate-900/80 border border-slate-800 space-y-1">
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="font-bold text-slate-200">{leg.symbol || `Leg #${lIdx + 1}`}</span>
                            <span className={`px-1.5 py-0.2 rounded font-bold uppercase text-[10px] ${
                              leg.direction === "buy" ? "text-emerald-300 bg-emerald-950/60" : "text-rose-300 bg-rose-950/60"
                            }`}>
                              {leg.direction}
                            </span>
                          </div>
                          <div className="flex justify-between text-[10px] text-slate-400">
                            <span>Strike: ${leg.strike?.toLocaleString()}</span>
                            <span>{leg.option_type?.toUpperCase()}</span>
                            <span>Ask/Bid: ${leg.order_price}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Algorithmic Rationale */}
                <p className="text-xs text-slate-300 bg-slate-900/60 p-2.5 rounded border border-slate-800/80 leading-relaxed">
                  {rec.rationale}
                </p>

                {/* Transparent Cost Drag Breakdown */}
                <div className="space-y-1.5 font-mono-num text-xs">
                  <span className="text-[10px] uppercase font-semibold text-slate-400">Cost Deduction Breakdown</span>
                  <div className="grid grid-cols-3 sm:grid-cols-6 gap-1 text-[11px]">
                    <div className="bg-slate-900/80 p-1.5 rounded text-center border border-slate-800">
                      <span className="text-slate-500 block text-[9px]">SPREAD</span>
                      <span className="text-rose-300">-{(costs.spread * 100 || 0).toFixed(2)}%</span>
                    </div>
                    <div className="bg-slate-900/80 p-1.5 rounded text-center border border-slate-800">
                      <span className="text-slate-500 block text-[9px]">FEES</span>
                      <span className="text-rose-300">-{(costs.fee * 100 || 0).toFixed(2)}%</span>
                    </div>
                    <div className="bg-slate-900/80 p-1.5 rounded text-center border border-slate-800">
                      <span className="text-slate-500 block text-[9px]">SLIPPAGE</span>
                      <span className="text-rose-300">-{(costs.slippage * 100 || 0).toFixed(2)}%</span>
                    </div>
                    <div className="bg-slate-900/80 p-1.5 rounded text-center border border-slate-800">
                      <span className="text-slate-500 block text-[9px]">HEDGE</span>
                      <span className="text-rose-300">-{(costs.hedge * 100 || 0).toFixed(2)}%</span>
                    </div>
                    <div className="bg-slate-900/80 p-1.5 rounded text-center border border-slate-800">
                      <span className="text-slate-500 block text-[9px]">CARRY</span>
                      <span className="text-rose-300">-{(costs.carry * 100 || 0).toFixed(2)}%</span>
                    </div>
                    <div className="bg-slate-900/80 p-1.5 rounded text-center border border-slate-800">
                      <span className="text-slate-500 block text-[9px]">UNCERTAINTY</span>
                      <span className="text-rose-300">-{(costs.uncertainty_penalty * 100 || 0).toFixed(2)}%</span>
                    </div>
                  </div>
                </div>

                {/* Greeks & Risk Metrics */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono-num pt-1">
                  <div className="bg-slate-900/40 p-2 rounded border border-slate-800/80">
                    <span className="text-slate-500 text-[10px] block">DELTA</span>
                    <span className={`font-semibold ${Math.abs(greeks.delta) < 0.1 ? "text-cyan-300" : "text-slate-200"}`}>
                      {greeks.delta > 0 ? `+${greeks.delta}` : greeks.delta}
                    </span>
                  </div>
                  <div className="bg-slate-900/40 p-2 rounded border border-slate-800/80">
                    <span className="text-slate-500 text-[10px] block">VEGA</span>
                    <span className="font-semibold text-slate-200">${greeks.vega}</span>
                  </div>
                  <div className="bg-slate-900/40 p-2 rounded border border-slate-800/80">
                    <span className="text-slate-500 text-[10px] block">MARGIN REQ</span>
                    <span className="font-semibold text-slate-200">${rec.initial_margin?.toLocaleString()}</span>
                  </div>
                  <div className="bg-slate-900/40 p-2 rounded border border-slate-800/80">
                    <span className="text-slate-500 text-[10px] block">STRESS LOSS</span>
                    <span className="font-semibold text-rose-400">-${rec.stress_max_loss?.toLocaleString()}</span>
                  </div>
                </div>

                {/* Status & Actions Footer */}
                <div className="flex items-center justify-between pt-2 border-t border-slate-800">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs text-slate-400">Status:</span>
                    <span className={`text-xs font-bold uppercase font-mono-num px-2 py-0.5 rounded ${
                      rec.status === "approved" ? "bg-emerald-950 text-emerald-300 border border-emerald-800" :
                      rec.status === "rejected" ? "bg-rose-950 text-rose-300 border border-rose-800" :
                      "bg-amber-950 text-amber-300 border border-amber-800"
                    }`}>
                      {rec.status}
                    </span>
                  </div>

                  {isPending && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setRejectModalRec(rec)}
                        className="px-3 py-1.5 rounded-md bg-rose-950/60 hover:bg-rose-900/80 text-rose-300 border border-rose-800 text-xs font-medium transition"
                      >
                        Reject
                      </button>

                      <button
                        onClick={() => onOpenReview(rec)}
                        className="px-3.5 py-1.5 rounded-md bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-md shadow-cyan-600/20 transition flex items-center gap-1"
                      >
                        <span>{isMultiLeg ? "Review Multi-Leg" : "Review & Approve"}</span>
                        <ChevronRight className="h-3 w-3" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Rejection Modal with Mandatory Reason */}
      {rejectModalRec && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-5 space-y-4">
            <div className="flex items-center gap-2 text-rose-400">
              <AlertCircle className="h-5 w-5" />
              <h3 className="font-bold text-base text-slate-100">Reject Recommendation</h3>
            </div>

            <p className="text-xs text-slate-300">
              Please enter the mandatory reason for rejecting this recommendation. An immutable audit record will be logged.
            </p>

            <textarea
              rows={3}
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g., Spread too wide, Liquidity insufficient, Skew profile unfavorable..."
              className="w-full p-2.5 rounded bg-slate-950 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-rose-500"
            />

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setRejectModalRec(null)}
                className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReject}
                disabled={!rejectReason.trim()}
                className="px-4 py-1.5 rounded bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white text-xs font-semibold"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
