"use client";

import React, { useState } from "react";
import {
  FileText, Shield, Play, Pause, AlertTriangle, CheckCircle2,
  DollarSign, Activity, Lock, RefreshCw, Layers
} from "lucide-react";
import { api } from "@/lib/api";

interface MandatesViewProps {
  mandates: any[];
  onRefresh: () => void;
}

export default function MandatesView({ mandates, onRefresh }: MandatesViewProps) {
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const handleToggleStatus = async (mandate: any) => {
    setActionLoading(mandate.id);
    try {
      if (mandate.status === "active") {
        await api.pauseMandate(mandate.id);
      } else {
        await api.activateMandate(mandate.id);
      }
      onRefresh();
    } catch (e) {
      console.error("Failed to toggle mandate:", e);
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass-panel p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-100">Algorithmic Mandates & Strategy Governance</h2>
            <span className="text-xs font-mono-num px-2 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-300">
              {mandates.length} Registered
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Governed operating envelopes defining permitted instruments, risk limits, capital bounds, and execution mode.
          </p>
        </div>

        <button
          onClick={onRefresh}
          className="px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition flex items-center gap-1.5"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Refresh Mandates</span>
        </button>
      </div>

      {/* Mandate Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {mandates.map((m: any) => {
          const isActive = m.status === "active";
          const isBtc = m.id.includes("btc") || m.strategy.includes("btc");

          return (
            <div
              key={m.id}
              className="glass-panel p-5 space-y-4 hover:border-slate-700 transition"
            >
              {/* Card Header */}
              <div className="flex items-start justify-between border-b border-slate-800 pb-3">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono-num ${
                      isBtc ? "bg-amber-950 text-amber-300 border border-amber-800" : "bg-cyan-950 text-cyan-300 border border-cyan-800"
                    }`}>
                      {isBtc ? "BTC" : "ETH"}
                    </span>

                    <h3 className="font-bold text-slate-100 text-base font-mono-num">{m.id}</h3>

                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                      isActive ? "bg-emerald-950 text-emerald-300 border border-emerald-800" : "bg-amber-950 text-amber-300 border border-amber-800"
                    }`}>
                      {m.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1 font-mono-num">
                    Strategy: <span className="text-slate-200 font-semibold">{m.strategy}</span>
                  </p>
                </div>

                <button
                  onClick={() => handleToggleStatus(m)}
                  disabled={actionLoading === m.id}
                  className={`px-3 py-1.5 rounded text-xs font-semibold flex items-center gap-1.5 transition ${
                    isActive
                      ? "bg-amber-950/80 hover:bg-amber-900 border border-amber-800 text-amber-300"
                      : "bg-emerald-950/80 hover:bg-emerald-900 border border-emerald-800 text-emerald-300"
                  }`}
                >
                  {isActive ? (
                    <>
                      <Pause className="h-3.5 w-3.5" />
                      <span>{actionLoading === m.id ? "Pausing..." : "Pause"}</span>
                    </>
                  ) : (
                    <>
                      <Play className="h-3.5 w-3.5" />
                      <span>{actionLoading === m.id ? "Resuming..." : "Resume"}</span>
                    </>
                  )}
                </button>
              </div>

              {/* Capital & Limits Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono-num text-xs">
                <div className="bg-slate-900/60 p-2.5 rounded border border-slate-800">
                  <span className="text-slate-500 text-[10px] block">CAPITAL LIMIT</span>
                  <span className="font-bold text-slate-100">${(m.capital_limit || 250000).toLocaleString()}</span>
                </div>
                <div className="bg-slate-900/60 p-2.5 rounded border border-slate-800">
                  <span className="text-slate-500 text-[10px] block">MAX DELTA</span>
                  <span className="font-bold text-slate-200">±{m.max_delta_limit?.toFixed(1) || "5.0"}</span>
                </div>
                <div className="bg-slate-900/60 p-2.5 rounded border border-slate-800">
                  <span className="text-slate-500 text-[10px] block">MAX VEGA</span>
                  <span className="font-bold text-slate-200">${(m.max_vega_limit || 50000).toLocaleString()}</span>
                </div>
                <div className="bg-slate-900/60 p-2.5 rounded border border-slate-800">
                  <span className="text-slate-500 text-[10px] block">MAX 1D VAR</span>
                  <span className="font-bold text-purple-300">${(m.max_var_limit || 100000).toLocaleString()}</span>
                </div>
              </div>

              {/* Permitted Scope & Venues */}
              <div className="space-y-2 text-xs font-mono-num bg-slate-900/40 p-3 rounded border border-slate-800/80">
                <div className="flex justify-between">
                  <span className="text-slate-400">Execution Mode:</span>
                  <span className="text-amber-400 font-semibold uppercase">{m.mode} (Live Disabled)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Hedge Permissions:</span>
                  <span className="text-emerald-400">{m.hedge_permissions}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Max Allowed Drawdown:</span>
                  <span className="text-slate-200">{((m.max_drawdown_limit || 0.15) * 100).toFixed(0)}%</span>
                </div>
                <div className="flex justify-between items-center pt-1 border-t border-slate-800">
                  <span className="text-slate-400">Permitted Venues:</span>
                  <div className="flex gap-1">
                    {(m.venues || ["deribit"]).map((v: string) => (
                      <span key={v} className="px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 text-[10px] uppercase">
                        {v}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Allowed Instruments:</span>
                  <div className="flex gap-1 flex-wrap justify-end">
                    {(m.allowed_instruments || []).map((inst: string) => (
                      <span key={inst} className="px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 text-[10px]">
                        {inst}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
