const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer dev-token",
    ...(options.headers || {}),
  };

  try {
    const res = await fetch(url, { ...options, headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail?.message || err.detail || `Request failed with status ${res.status}`);
    }
    const json = await res.json();
    return json.data !== undefined ? json.data : json;
  } catch (e: any) {
    console.error(`API Error on ${endpoint}:`, e);
    throw e;
  }
}

export const api = {
  getMarketHealth: () => fetchApi("/market/health"),
  getInstruments: (underlying = "BTC") => fetchApi(`/instruments?underlying=${underlying}`),
  getSurface: (underlying = "BTC") => fetchApi(`/surfaces/${underlying}`),
  generateForecast: (underlying = "BTC", horizon = 3600) =>
    fetchApi("/forecasts/realized-volatility", {
      method: "POST",
      body: JSON.stringify({ underlying, horizon_seconds: horizon }),
    }),
  getRecommendations: (status?: string, underlying?: string, watchlistOnly?: boolean) => {
    const params = new URLSearchParams();
    if (status) params.append("status", status);
    if (underlying) params.append("underlying", underlying);
    if (watchlistOnly) params.append("watchlist_only", "true");
    const query = params.toString();
    return fetchApi(`/recommendations${query ? `?${query}` : ""}`);
  },
  generateRecommendations: (underlying?: string) =>
    fetchApi(`/recommendations/generate${underlying ? `?underlying=${underlying}` : ""}`, { method: "POST" }),
  toggleWatchlist: (id: string) =>
    fetchApi(`/recommendations/${id}/watchlist`, { method: "POST" }),
  approveRecommendation: (id: string, payload: any) =>
    fetchApi(`/recommendations/${id}/approve`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  rejectRecommendation: (id: string, reason: string) =>
    fetchApi(`/recommendations/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  editRecommendation: (id: string, payload: any) =>
    fetchApi(`/recommendations/${id}/edit`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  rebalanceDelta: (underlying = "BTC") =>
    fetchApi(`/portfolio/rebalance?underlying=${underlying}`, { method: "POST" }),
  getPortfolioRisk: () => fetchApi("/portfolio/risk"),
  runStressTest: (targetType = "portfolio", targetId?: string) =>
    fetchApi("/risk/stress-runs", {
      method: "POST",
      body: JSON.stringify({ target_type: targetType, target_id: targetId }),
    }),
  triggerEmergencyStop: (reason: string) =>
    fetchApi("/controls/emergency-stop", {
      method: "POST",
      body: JSON.stringify({ reason, confirmed: true }),
    }),
  resetEmergencyStop: () =>
    fetchApi("/controls/emergency-stop/reset", { method: "POST" }),
  getOperatingMode: () => fetchApi("/controls/mode"),
  switchOperatingMode: (mode: string, reason?: string) =>
    fetchApi("/controls/mode", {
      method: "POST",
      body: JSON.stringify({ mode, reason }),
    }),
  getMandates: () => fetchApi("/mandates"),
  pauseMandate: (id: string) => fetchApi(`/mandates/${id}/pause`, { method: "POST" }),
  activateMandate: (id: string) => fetchApi(`/mandates/${id}/activate`, { method: "POST" }),
  getPaperOrders: () => fetchApi("/paper/orders"),
  getPaperPositions: () => fetchApi("/paper/positions"),
  getPnLReport: () => fetchApi("/reports/pnl"),
  getAuditEvents: () => fetchApi("/audit/events?limit=50"),
  replayTick: (batchSize = 10) =>
    fetchApi(`/replay/tick?batch_size=${batchSize}`, { method: "POST" }),
};
