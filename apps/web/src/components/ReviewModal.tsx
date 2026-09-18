"use client";

import React, { useState, useEffect } from "react";
import {
  X, CheckCircle2, AlertTriangle, ShieldCheck, DollarSign,
  Activity, ArrowRight, Zap, RefreshCw
} from "lucide-react";
import { api } from "@/lib/api";

interface ReviewModalProps {
  rec: any;
  onClose: () => void;
  onApproved: () => void;
}

export default function ReviewModal({ rec, onClose, onApproved }: ReviewModalProps) {
  const leg = rec.legs?.[0] || {};
  const [quantity, setQuantity] = useState<number>(leg.quantity || 1.0);
  const [priceLimit, setPriceLimit] = useState<number>(leg.order_price || 2000.0);
  const [comment, setComment] = useState<string>("Approved after liquidity and risk review.");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Recalculated metrics state
  const [recalc, setRecalc] = useState<{
    delta: number;
    gamma: number;
    vega: number;
    theta: number;
    margin: number;
    stressLoss: number;
    netEdge: number;
  }>({
    delta: rec.delta || 0,
    gamma: rec.gamma || 0,
    vega: rec.vega || 0,
    theta: rec.theta || 0,
    margin: rec.initial_margin || 0,
    stressLoss: rec.stress_max_loss || 0,
    netEdge: rec.net_edge || 0,
  });

  useEffect(() => {
    // Recalculate metrics locally on input change
    const baseQty = leg.quantity || 1.0;
    const ratio = quantity / baseQty;
    const newDelta = (rec.delta || 0) * ratio;
    const newGamma = (rec.gamma || 0) * ratio;
    const newVega = (rec.vega || 0) * ratio;
    const newTheta = (rec.theta || 0) * ratio;
    const newMargin = (rec.initial_margin || 0) * ratio;
    const newStress = (rec.stress_max_loss || 0) * ratio;

    // Net edge adjusts slightly with sizing due to slippage
    const slippagePenalty = 0.0002 * (1.0 + 0.1 * quantity);
    const newNetEdge = Math.max(0.001, (rec.gross_edge || 0.1) - (rec.spread_cost + rec.fee_cost + slippagePenalty + rec.hedge_cost + rec.carry_cost + rec.uncertainty_penalty));

    setRecalc({
      delta: newDelta,
      gamma: newGamma,
      vega: newVega,
      theta: newTheta,
      margin: newMargin,
      stressLoss: newStress,
      netEdge: newNetEdge,
    });
  }, [quantity, priceLimit, rec]);

  const handleApprove = async () => {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      // First commit edits if changed
      if (quantity !== leg.quantity || priceLimit !== leg.order_price) {
        await api.editRecommendation(rec.id, {
          quantity,
          price_limit: priceLimit,
          edit_reason: "Manual adjustment during review modal",
        });
      }

      // Submit approval
      await api.approveRecommendation(rec.id, {
        mode: "paper",
        quantity_override: quantity,
        price_limit_override: priceLimit,
        hedge_permission: "within_mandate",
        comment: comment.trim(),
      });

      onApproved();
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || "Approval rejected by risk engine or conflict.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 overflow-y-auto">
      <div className="bg-[#101726] border border-slate-700 rounded-2xl max-w-2xl w-full p-6 space-y-5 shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase font-bold px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono-num">
                {rec.strategy_type?.replace("_", " ")}
              </span>
              <h2 className="text-lg font-bold text-slate-100 font-mono-num">
                {leg.symbol || `BTC Option Strike $${leg.strike}`}
              </h2>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Review and adjust assumptions. Pre-execution independent risk checks will validate before paper submission.
            </p>
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Error Notification if Risk Check Fails */}
        {errorMsg && (
          <div className="p-3.5 rounded-lg bg-rose-950/80 border border-rose-600 text-rose-200 text-xs flex items-center gap-2.5">
            <AlertTriangle className="h-5 w-5 text-rose-400 shrink-0" />
            <div>
              <span className="font-bold block">Pre-Execution Risk Rejection</span>
              <span>{errorMsg}</span>
            </div>
          </div>
        )}

        {/* Parameter Edit Inputs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5 font-mono-num">
            <label className="text-xs text-slate-300 flex justify-between">
              <span>Order Quantity (Contracts):</span>
              <span className="text-cyan-400 font-bold">{quantity} BTC</span>
            </label>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min="0.5"
                max="10.0"
                step="0.5"
                value={quantity}
                onChange={(e) => setQuantity(parseFloat(e.target.value))}
                className="w-full accent-cyan-500"
              />
              <input
                type="number"
                min="0.1"
                max="50.0"
                step="0.5"
                value={quantity}
                onChange={(e) => setQuantity(parseFloat(e.target.value) || 1)}
                className="w-20 p-1.5 rounded bg-slate-900 border border-slate-700 text-slate-100 text-xs text-right"
              />
            </div>
          </div>

          <div className="space-y-1.5 font-mono-num">
            <label className="text-xs text-slate-300 flex justify-between">
              <span>Limit Price Assumption ($):</span>
              <span className="text-cyan-400 font-bold">${priceLimit}</span>
            </label>
            <input
              type="number"
              value={priceLimit}
              onChange={(e) => setPriceLimit(parseFloat(e.target.value) || 0)}
              className="w-full p-1.5 rounded bg-slate-900 border border-slate-700 text-slate-100 text-xs font-bold"
            />
          </div>
        </div>

        {/* Dynamic Recalculated Greeks & Risk Matrix */}
        <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-xs border-b border-slate-800 pb-2">
            <span className="font-semibold text-slate-200 flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5 text-cyan-400" />
              Real-Time Impact & Re-calculated Greeks
            </span>
            <span className="font-mono-num text-emerald-400 font-bold">
              Net Edge: +{(recalc.netEdge * 100).toFixed(2)}%
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono-num">
            <div className="bg-slate-950 p-2 rounded border border-slate-800/80">
              <span className="text-slate-500 text-[10px] block">DELTA</span>
              <span className="font-bold text-slate-200">
                {recalc.delta > 0 ? `+${recalc.delta.toFixed(3)}` : recalc.delta.toFixed(3)}
              </span>
            </div>
            <div className="bg-slate-950 p-2 rounded border border-slate-800/80">
              <span className="text-slate-500 text-[10px] block">VEGA</span>
              <span className="font-bold text-slate-200">${recalc.vega.toFixed(0)}</span>
            </div>
            <div className="bg-slate-950 p-2 rounded border border-slate-800/80">
              <span className="text-slate-500 text-[10px] block">REQUIRED MARGIN</span>
              <span className="font-bold text-slate-200">${recalc.margin.toLocaleString()}</span>
            </div>
            <div className="bg-slate-950 p-2 rounded border border-slate-800/80">
              <span className="text-slate-500 text-[10px] block">STRESS MAX LOSS</span>
              <span className="font-bold text-rose-400">-${recalc.stressLoss.toLocaleString()}</span>
            </div>
          </div>
        </div>

        {/* Audit Comment */}
        <div className="space-y-1 text-xs">
          <label className="text-slate-300 font-medium">Approval Audit Rationale (Mandatory Context):</label>
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="w-full p-2 rounded bg-slate-950 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
          />
        </div>

        {/* Action Controls */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-800">
          <div className="text-[11px] text-slate-400 font-mono-num flex items-center gap-1.5">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <span>Target Execution: <strong>Paper Simulator (No Live Routing)</strong></span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              disabled={isSubmitting}
              className="px-3.5 py-2 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition"
            >
              Cancel
            </button>

            <button
              onClick={handleApprove}
              disabled={isSubmitting}
              className="px-5 py-2 rounded-md bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold shadow-lg shadow-cyan-600/30 transition flex items-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  <span>Simulating Fill...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4" />
                  <span>Approve & Execute Paper Order</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
