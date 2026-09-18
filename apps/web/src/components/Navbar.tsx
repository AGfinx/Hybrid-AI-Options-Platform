"use client";

import React from "react";
import {
  Shield, AlertTriangle, RefreshCw, Play, Zap, ShieldAlert,
  Activity, CheckCircle2, ChevronDown
} from "lucide-react";

interface NavbarProps {
  mode: string;
  onModeChange: (newMode: string) => void;
  marketHealth: any;
  onReplayTick: () => void;
  onGenerateRecs: () => void;
  onEmergencyStopClick: () => void;
  isReplaying: boolean;
  isGenerating: boolean;
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export default function Navbar({
  mode,
  onModeChange,
  marketHealth,
  onReplayTick,
  onGenerateRecs,
  onEmergencyStopClick,
  isReplaying,
  isGenerating,
  activeTab,
  setActiveTab,
}: NavbarProps) {
  const tabs = [
    { id: "cockpit", label: "Cockpit" },
    { id: "surface", label: "Volatility & SVI" },
    { id: "recommendations", label: "Opportunities" },
    { id: "mandates", label: "Mandates" },
    { id: "paper", label: "Paper Trading" },
    { id: "risk", label: "Risk & VaR" },
    { id: "audit", label: "Audit Trail" },
  ];

  const modes = [
    { id: "analytics", label: "Analytics Only", desc: "No recommendations or paper orders" },
    { id: "recommendation", label: "Recommendation Mode (Default)", desc: "Human approval required" },
    { id: "assisted", label: "Assisted Paper", desc: "Mandate guided execution" },
    { id: "bounded_automation", label: "Bounded Automation", desc: "Paper simulation only; live disabled" },
  ];

  const [modeMenuOpen, setModeMenuOpen] = React.useState(false);

  return (
    <header className="border-b border-slate-800 bg-[#0c121e]/90 backdrop-blur sticky top-0 z-40 px-4 py-2.5">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Brand & Mode */}
        <div className="flex items-center gap-3 w-full md:w-auto justify-between md:justify-start">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-cyan-500/20">
              Ω
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-100 tracking-wide text-sm md:text-base">
                  HYBRID AI OPTIONS
                </span>
                <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/60 font-semibold font-mono-num">
                  BTC & ETH v2.0
                </span>
              </div>
              <p className="text-[11px] text-slate-400">Human-in-the-Loop Quant Trading</p>
            </div>
          </div>

          {/* Mode Badge Dropdown */}
          <div className="relative">
            <button
              onClick={() => setModeMenuOpen(!modeMenuOpen)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-slate-900 border border-slate-700 hover:border-slate-600 text-slate-200 transition"
            >
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="capitalize">{mode.replace("_", " ")}</span>
              <ChevronDown className="h-3 w-3 text-slate-400" />
            </button>

            {modeMenuOpen && (
              <div className="absolute left-0 mt-1 w-64 bg-slate-900 border border-slate-700 rounded-lg shadow-2xl p-1 z-50">
                <div className="text-[10px] uppercase font-semibold text-slate-400 px-2 py-1">Operating Mode</div>
                {modes.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => {
                      onModeChange(m.id);
                      setModeMenuOpen(false);
                    }}
                    className={`w-full text-left px-2.5 py-1.5 rounded text-xs transition flex flex-col ${
                      mode === m.id ? "bg-cyan-950/60 text-cyan-300 border border-cyan-800/40" : "text-slate-300 hover:bg-slate-800"
                    }`}
                  >
                    <span className="font-semibold">{m.label}</span>
                    <span className="text-[10px] text-slate-400">{m.desc}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1 bg-slate-900/80 p-1 rounded-lg border border-slate-800 text-xs overflow-x-auto max-w-full">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-md font-medium transition whitespace-nowrap ${
                activeTab === tab.id
                  ? "bg-cyan-600 text-white shadow-sm shadow-cyan-500/30"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Market Status, Ticker & Emergency Stop */}
        <div className="flex items-center gap-2">
          {/* Feed Quality Pill */}
          <div className="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded-md bg-slate-900/90 border border-slate-800 text-xs font-mono-num">
            <span className="text-slate-400">BTC Spot:</span>
            <span className="text-cyan-400 font-bold">
              ${marketHealth?.spot_price?.toLocaleString() || "65,000"}
            </span>
            <span className="text-slate-600">|</span>
            <span className="text-slate-400">Age:</span>
            <span className={marketHealth?.quote_age_seconds > 15 ? "text-rose-400" : "text-emerald-400"}>
              {marketHealth?.quote_age_seconds || "0.2"}s
            </span>
          </div>

          {/* Replay & Scan Buttons */}
          <button
            onClick={onReplayTick}
            disabled={isReplaying}
            title="Step synthetic market data forward"
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs transition border border-slate-700"
          >
            <RefreshCw className={`h-3 w-3 ${isReplaying ? "animate-spin text-cyan-400" : "text-slate-400"}`} />
            <span className="hidden sm:inline">Replay +10</span>
          </button>

          <button
            onClick={onGenerateRecs}
            disabled={isGenerating}
            title="Scan opportunity engine for new signals"
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-indigo-950 hover:bg-indigo-900 border border-indigo-700 text-indigo-200 text-xs transition"
          >
            <Zap className={`h-3 w-3 ${isGenerating ? "animate-bounce text-indigo-400" : "text-indigo-400"}`} />
            <span className="hidden sm:inline">Scan Vol</span>
          </button>

          {/* Emergency Stop Button */}
          <button
            onClick={onEmergencyStopClick}
            className="flex items-center gap-1.5 px-3 py-1 rounded bg-rose-600/90 hover:bg-rose-500 text-white font-semibold text-xs transition shadow-lg shadow-rose-600/20 border border-rose-500"
          >
            <ShieldAlert className="h-3.5 w-3.5" />
            <span>EMERGENCY STOP</span>
          </button>
        </div>
      </div>
    </header>
  );
}
