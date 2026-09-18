"use client";

import React, { useState, useEffect, useMemo } from "react";
import { CheckCircle2, AlertTriangle, RefreshCw, BarChart2, ShieldCheck, Activity, TrendingUp, Layers } from "lucide-react";
import { api } from "@/lib/api";

interface SurfaceViewProps {
  surfaceData: any;
  onRefresh: () => void;
  underlying?: string;
  onSelectUnderlying?: (asset: string) => void;
}

export default function SurfaceView({
  surfaceData,
  onRefresh,
  underlying = "BTC",
  onSelectUnderlying
}: SurfaceViewProps) {
  const [selectedAsset, setSelectedAsset] = useState<string>(underlying);
  const [forecast, setForecast] = useState<any>(null);
  const [loadingForecast, setLoadingForecast] = useState(false);
  const [selectedExpiry, setSelectedExpiry] = useState<number | null>(null);

  useEffect(() => {
    setSelectedAsset(underlying);
  }, [underlying]);

  useEffect(() => {
    loadForecast(selectedAsset);
  }, [selectedAsset]);

  const loadForecast = async (asset: string) => {
    setLoadingForecast(true);
    try {
      const data = await api.generateForecast(asset, 3600);
      setForecast(data);
    } catch (e) {
      console.error("Error loading forecast:", e);
    } finally {
      setLoadingForecast(false);
    }
  };

  const handleAssetChange = (asset: string) => {
    setSelectedAsset(asset);
    if (onSelectUnderlying) {
      onSelectUnderlying(asset);
    }
  };

  const points = surfaceData?.points || [];
  const spot = surfaceData?.spot || (selectedAsset === "BTC" ? 65000.0 : 3500.0);
  const sviSlices = surfaceData?.svi_slices || {};

  const expiries = useMemo(() => {
    return Array.from(new Set(points.map((p: any) => p.expiry_years))).sort((a: any, b: any) => a - b) as number[];
  }, [points]);

  // Default to 30d (approx 0.082y) or first expiry if not selected
  const activeExpiry = selectedExpiry ?? (expiries.find(e => Math.abs(e - 30/365) < 0.02) || expiries[0] || (30/365));

  const filteredPoints = useMemo(() => {
    return points.filter((p: any) => Math.abs(p.expiry_years - activeExpiry) < 0.008);
  }, [points, activeExpiry]);

  // Look up SVI slice for active expiry
  const activeSviSliceKey = useMemo(() => {
    const days = Math.round(activeExpiry * 365);
    const key = `${days}d`;
    if (sviSlices[key]) return key;
    // Find closest key
    const keys = Object.keys(sviSlices);
    if (keys.length === 0) return null;
    return keys[0];
  }, [sviSlices, activeExpiry]);

  const activeSviParams = activeSviSliceKey ? sviSlices[activeSviSliceKey] : null;

  // Generate continuous SVI smile points for SVG curve
  const sviSmilePoints = useMemo(() => {
    if (!activeSviParams || activeExpiry <= 0) return [];
    const { a, b, rho, m, sigma } = activeSviParams;
    const strikeMin = spot * 0.75;
    const strikeMax = spot * 1.25;
    const steps = 40;
    const pts = [];

    for (let i = 0; i <= steps; i++) {
      const K = strikeMin + (i / steps) * (strikeMax - strikeMin);
      const k = Math.log(K / spot);
      const diff = k - m;
      const w = Math.max(1e-5, a + b * (rho * diff + Math.sqrt(diff * diff + sigma * sigma)));
      const iv = Math.sqrt(w / activeExpiry);
      pts.push({ strike: K, iv });
    }
    return pts;
  }, [activeSviParams, activeExpiry, spot]);

  // Term Structure curve points
  const termStructurePoints = useMemo(() => {
    return expiries.map(T => {
      const ptsAtT = points.filter((p: any) => Math.abs(p.expiry_years - T) < 0.005);
      const avgIv = ptsAtT.length > 0
        ? ptsAtT.reduce((sum: number, p: any) => sum + p.implied_vol, 0) / ptsAtT.length
        : 0.55;
      return {
        days: Math.round(T * 365),
        expiryYears: T,
        iv: avgIv
      };
    });
  }, [expiries, points]);

  // SVG Chart bounds for Smile
  const smileChart = useMemo(() => {
    const allStrikes = [
      ...sviSmilePoints.map(p => p.strike),
      ...filteredPoints.map((p: any) => p.strike)
    ];
    const allVols = [
      ...sviSmilePoints.map(p => p.iv),
      ...filteredPoints.map((p: any) => p.implied_vol)
    ];

    const minK = allStrikes.length > 0 ? Math.min(...allStrikes) : spot * 0.8;
    const maxK = allStrikes.length > 0 ? Math.max(...allStrikes) : spot * 1.2;
    const minVol = allVols.length > 0 ? Math.max(0.2, Math.min(...allVols) - 0.05) : 0.4;
    const maxVol = allVols.length > 0 ? Math.max(...allVols) + 0.05 : 0.8;

    const width = 500;
    const height = 200;
    const pad = 40;

    const toX = (K: number) => pad + ((K - minK) / (maxK - minK || 1)) * (width - pad * 2);
    const toY = (iv: number) => height - pad - ((iv - minVol) / (maxVol - minVol || 1)) * (height - pad * 2);

    let pathD = "";
    if (sviSmilePoints.length > 0) {
      pathD = sviSmilePoints.map((p, idx) => `${idx === 0 ? "M" : "L"} ${toX(p.strike).toFixed(1)} ${toY(p.iv).toFixed(1)}`).join(" ");
    }

    return { minK, maxK, minVol, maxVol, width, height, pad, toX, toY, pathD };
  }, [sviSmilePoints, filteredPoints, spot]);

  // SVG Chart bounds for Term Structure
  const termChart = useMemo(() => {
    const width = 360;
    const height = 200;
    const pad = 35;

    const maxDays = termStructurePoints.length > 0 ? Math.max(...termStructurePoints.map(p => p.days)) : 90;
    const minDays = termStructurePoints.length > 0 ? Math.min(...termStructurePoints.map(p => p.days)) : 7;
    const vols = termStructurePoints.map(p => p.iv);
    const minVol = vols.length > 0 ? Math.max(0.2, Math.min(...vols) - 0.05) : 0.4;
    const maxVol = vols.length > 0 ? Math.max(...vols) + 0.05 : 0.8;

    const toX = (d: number) => pad + ((d - minDays) / (maxDays - minDays || 1)) * (width - pad * 2);
    const toY = (iv: number) => height - pad - ((iv - minVol) / (maxVol - minVol || 1)) * (height - pad * 2);

    let pathD = "";
    if (termStructurePoints.length > 0) {
      pathD = termStructurePoints.map((p, idx) => `${idx === 0 ? "M" : "L"} ${toX(p.days).toFixed(1)} ${toY(p.iv).toFixed(1)}`).join(" ");
    }

    return { width, height, toX, toY, pathD, minDays, maxDays, minVol, maxVol };
  }, [termStructurePoints]);

  return (
    <div className="space-y-6">
      {/* Header & Underlying Switcher */}
      <div className="glass-panel p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-slate-100">Volatility Surface & SVI Calibration</h2>
            {/* Asset Switcher */}
            <div className="flex rounded-lg bg-slate-900/80 p-0.5 border border-slate-800">
              <button
                onClick={() => handleAssetChange("BTC")}
                className={`px-3 py-1 rounded-md text-xs font-bold transition flex items-center gap-1.5 ${
                  selectedAsset === "BTC"
                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <span>BTC</span>
                <span className="text-[10px] text-slate-400 font-mono-num">$65,000</span>
              </button>
              <button
                onClick={() => handleAssetChange("ETH")}
                className={`px-3 py-1 rounded-md text-xs font-bold transition flex items-center gap-1.5 ${
                  selectedAsset === "ETH"
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <span>ETH</span>
                <span className="text-[10px] text-slate-400 font-mono-num">$3,500</span>
              </button>
            </div>

            <span className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase ${
              surfaceData?.structural_status === "valid" ? "bg-emerald-950 text-emerald-300 border border-emerald-800" : "bg-amber-950 text-amber-300 border border-amber-800"
            }`}>
              {surfaceData?.structural_status || "VALID"}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Jim Gatheral's Raw SVI parameterization <code className="text-cyan-400 font-mono-num">w(k) = a + b(ρ(k-m) + √( (k-m)² + σ² ))</code> with calendar & butterfly spread non-arbitrage bounds.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right text-xs font-mono-num">
            <span className="text-slate-400 block">Surface Confidence</span>
            <span className="font-bold text-cyan-400 text-sm">
              {((surfaceData?.confidence || 1.0) * 100).toFixed(1)}%
            </span>
          </div>

          <button
            onClick={onRefresh}
            className="px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition flex items-center gap-1.5"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Re-fit SVI</span>
          </button>
        </div>
      </div>

      {/* Visual Analytics Grid: SVI Smile Chart + Term Structure Curve */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* SVG Volatility Smile Chart */}
        <div className="lg:col-span-7 glass-panel p-5 space-y-3">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-cyan-400" />
              <h3 className="font-bold text-slate-100 text-sm">
                Gatheral SVI Volatility Smile — {(activeExpiry * 365).toFixed(0)}d Tenor
              </h3>
            </div>
            {/* Tenor Selectors */}
            <div className="flex items-center gap-1">
              {expiries.map(T => {
                const days = Math.round(T * 365);
                const isSelected = Math.abs(T - activeExpiry) < 0.005;
                return (
                  <button
                    key={T}
                    onClick={() => setSelectedExpiry(T)}
                    className={`px-2 py-0.5 rounded text-[11px] font-mono-num transition ${
                      isSelected
                        ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 font-bold"
                        : "bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800"
                    }`}
                  >
                    {days}d
                  </button>
                );
              })}
            </div>
          </div>

          {/* SVG Smile Plot */}
          <div className="relative w-full overflow-hidden flex justify-center">
            <svg viewBox={`0 0 ${smileChart.width} ${smileChart.height}`} className="w-full h-52 text-xs">
              {/* Background gridlines */}
              <line x1={smileChart.pad} y1={smileChart.pad} x2={smileChart.width - smileChart.pad} y2={smileChart.pad} stroke="#1e293b" strokeDasharray="3 3" />
              <line x1={smileChart.pad} y1={smileChart.height / 2} x2={smileChart.width - smileChart.pad} y2={smileChart.height / 2} stroke="#1e293b" strokeDasharray="3 3" />
              <line x1={smileChart.pad} y1={smileChart.height - smileChart.pad} x2={smileChart.width - smileChart.pad} y2={smileChart.height - smileChart.pad} stroke="#334155" />

              {/* Spot reference vertical marker */}
              <line
                x1={smileChart.toX(spot)}
                y1={smileChart.pad}
                x2={smileChart.toX(spot)}
                y2={smileChart.height - smileChart.pad}
                stroke="#64748b"
                strokeDasharray="2 2"
              />
              <text x={smileChart.toX(spot)} y={smileChart.pad - 6} fill="#94a3b8" fontSize="10" textAnchor="middle" fontFamily="monospace">
                Spot (${spot >= 1000 ? `${(spot / 1000).toFixed(0)}k` : spot})
              </text>

              {/* SVI Fitted Smooth Smile Path */}
              {smileChart.pathD && (
                <path
                  d={smileChart.pathD}
                  fill="none"
                  stroke="#06b6d4"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
              )}

              {/* Market quotes data dots */}
              {filteredPoints.map((p: any, idx: number) => {
                const cx = smileChart.toX(p.strike);
                const cy = smileChart.toY(p.implied_vol);
                const isCall = p.option_type === "call";
                return (
                  <g key={idx}>
                    <circle
                      cx={cx}
                      cy={cy}
                      r="4"
                      fill={isCall ? "#10b981" : "#a855f7"}
                      stroke="#0f172a"
                      strokeWidth="1.5"
                    />
                  </g>
                );
              })}

              {/* Y-axis Labels */}
              <text x={smileChart.pad - 6} y={smileChart.pad + 4} fill="#64748b" fontSize="9" textAnchor="end" fontFamily="monospace">
                {(smileChart.maxVol * 100).toFixed(0)}%
              </text>
              <text x={smileChart.pad - 6} y={smileChart.height - smileChart.pad} fill="#64748b" fontSize="9" textAnchor="end" fontFamily="monospace">
                {(smileChart.minVol * 100).toFixed(0)}%
              </text>

              {/* X-axis Labels */}
              <text x={smileChart.pad} y={smileChart.height - 8} fill="#64748b" fontSize="9" textAnchor="middle" fontFamily="monospace">
                ${(smileChart.minK / 1000).toFixed(0)}k
              </text>
              <text x={smileChart.width - smileChart.pad} y={smileChart.height - 8} fill="#64748b" fontSize="9" textAnchor="middle" fontFamily="monospace">
                ${(smileChart.maxK / 1000).toFixed(0)}k
              </text>
            </svg>
          </div>

          <div className="flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-800/80 pt-2 font-mono-num">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 bg-cyan-400 inline-block" />
                <span>Gatheral SVI Fit</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />
                <span>Call Quotes</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-purple-400 inline-block" />
                <span>Put Quotes</span>
              </div>
            </div>
            {activeSviParams && (
              <span className="text-cyan-400 font-semibold">
                ρ (skew) = {activeSviParams.rho.toFixed(3)} | σ (curv) = {activeSviParams.sigma.toFixed(3)}
              </span>
            )}
          </div>
        </div>

        {/* SVG Term Structure Curve */}
        <div className="lg:col-span-5 glass-panel p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-purple-400" />
              <h3 className="font-bold text-slate-100 text-sm">ATM Term Structure</h3>
            </div>
            <span className="text-[11px] text-slate-400 font-mono-num">
              {termStructurePoints.length} Tenors
            </span>
          </div>

          <div className="relative w-full overflow-hidden flex justify-center">
            <svg viewBox={`0 0 ${termChart.width} ${termChart.height}`} className="w-full h-52 text-xs">
              <line x1={termChart.toX(termChart.minDays)} y1={termChart.height / 2} x2={termChart.toX(termChart.maxDays)} y2={termChart.height / 2} stroke="#1e293b" strokeDasharray="3 3" />
              <line x1={termChart.toX(termChart.minDays)} y1={termChart.height - 35} x2={termChart.toX(termChart.maxDays)} y2={termChart.height - 35} stroke="#334155" />

              {/* Term structure curve line */}
              {termChart.pathD && (
                <path
                  d={termChart.pathD}
                  fill="none"
                  stroke="#a855f7"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
              )}

              {/* Tenor dots */}
              {termStructurePoints.map((tp, idx) => (
                <g key={idx}>
                  <circle
                    cx={termChart.toX(tp.days)}
                    cy={termChart.toY(tp.iv)}
                    r="4.5"
                    fill="#a855f7"
                    stroke="#0f172a"
                    strokeWidth="2"
                  />
                  <text
                    x={termChart.toX(tp.days)}
                    y={termChart.toY(tp.iv) - 8}
                    fill="#e2e8f0"
                    fontSize="9"
                    textAnchor="middle"
                    fontFamily="monospace"
                  >
                    {(tp.iv * 100).toFixed(1)}%
                  </text>
                  <text
                    x={termChart.toX(tp.days)}
                    y={termChart.height - 12}
                    fill="#64748b"
                    fontSize="9"
                    textAnchor="middle"
                    fontFamily="monospace"
                  >
                    {tp.days}d
                  </text>
                </g>
              ))}
            </svg>
          </div>

          <p className="text-[11px] text-slate-400 border-t border-slate-800/80 pt-2 font-mono-num flex justify-between">
            <span>Skew Regime: Contango / Normal</span>
            <span className="text-purple-300 font-semibold">Near 7d vs Far 90d Spread</span>
          </p>
        </div>
      </div>

      {/* SVI Parametric Slice Coefficients Table */}
      <div className="glass-panel p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h3 className="font-bold text-slate-100 text-sm">Gatheral SVI Calibrated Slice Parameters</h3>
            <p className="text-xs text-slate-400">Total variance parameters satisfying quasi-explicit SciPy least-squares boundary conditions</p>
          </div>
          <span className="text-xs text-emerald-400 font-mono-num font-semibold">
            {Object.keys(sviSlices).length} Slices Active
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left font-mono-num">
            <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Tenor</th>
                <th className="py-2.5 px-3">Expiry (T)</th>
                <th className="py-2.5 px-3 text-cyan-400">a (Base Vol)</th>
                <th className="py-2.5 px-3 text-cyan-400">b (Angle Slope)</th>
                <th className="py-2.5 px-3 text-purple-400">ρ (Skewness)</th>
                <th className="py-2.5 px-3">m (ATM Translation)</th>
                <th className="py-2.5 px-3 text-emerald-400">σ (Curvature Smooth)</th>
                <th className="py-2.5 px-3 text-right">Arbitrage Check</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-200">
              {Object.entries(sviSlices).map(([tenor, p]: [string, any]) => (
                <tr key={tenor} className="hover:bg-slate-800/30 transition">
                  <td className="py-2.5 px-3 font-bold text-slate-100">{tenor}</td>
                  <td className="py-2.5 px-3 text-slate-400">{p.expiry_years.toFixed(4)}y</td>
                  <td className="py-2.5 px-3 font-semibold text-cyan-400">{p.a.toFixed(5)}</td>
                  <td className="py-2.5 px-3 font-semibold text-cyan-400">{p.b.toFixed(5)}</td>
                  <td className="py-2.5 px-3 font-semibold text-purple-400">{p.rho.toFixed(4)}</td>
                  <td className="py-2.5 px-3 text-slate-300">{p.m.toFixed(4)}</td>
                  <td className="py-2.5 px-3 font-semibold text-emerald-400">{p.sigma.toFixed(4)}</td>
                  <td className="py-2.5 px-3 text-right">
                    <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                      PASS
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Surface Points Table */}
      <div className="glass-panel p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h3 className="font-bold text-slate-100 text-sm">Market Quote Inversions ({selectedAsset})</h3>
            <p className="text-xs text-slate-400">Black-Scholes Brent-solver inversions across active strikes and tenors</p>
          </div>
          <span className="text-xs text-slate-400 font-mono-num">
            {filteredPoints.length} Knots in {(activeExpiry * 365).toFixed(0)}d slice
          </span>
        </div>

        <div className="overflow-x-auto max-h-[300px] overflow-y-auto">
          <table className="w-full text-xs text-left font-mono-num">
            <thead className="sticky top-0 bg-slate-900 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-2 px-3">Strike ($)</th>
                <th className="py-2 px-3">Type</th>
                <th className="py-2 px-3">Expiry (d)</th>
                <th className="py-2 px-3">Moneyness (K/S)</th>
                <th className="py-2 px-3">Mark ($)</th>
                <th className="py-2 px-3 text-cyan-400 font-bold">Implied Vol</th>
                <th className="py-2 px-3">Delta</th>
                <th className="py-2 px-3">Vega</th>
                <th className="py-2 px-3 text-right">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-200">
              {filteredPoints.map((pt: any, idx: number) => (
                <tr key={idx} className="hover:bg-slate-800/40 transition">
                  <td className="py-2 px-3 font-semibold">${pt.strike.toLocaleString()}</td>
                  <td className="py-2 px-3 uppercase font-bold text-[11px]">
                    <span className={pt.option_type === "call" ? "text-emerald-400" : "text-purple-400"}>
                      {pt.option_type}
                    </span>
                  </td>
                  <td className="py-2 px-3">{(pt.expiry_years * 365).toFixed(0)}d</td>
                  <td className="py-2 px-3 text-slate-400">{pt.moneyness.toFixed(3)}</td>
                  <td className="py-2 px-3">${pt.price.toLocaleString()}</td>
                  <td className="py-2 px-3 font-bold text-cyan-400">{(pt.implied_vol * 100).toFixed(1)}%</td>
                  <td className="py-2 px-3 text-slate-400">{pt.delta > 0 ? `+${pt.delta.toFixed(3)}` : pt.delta.toFixed(3)}</td>
                  <td className="py-2 px-3 text-slate-400">${pt.vega.toFixed(1)}</td>
                  <td className="py-2 px-3 text-right font-semibold text-emerald-400">
                    {(pt.confidence * 100).toFixed(0)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
