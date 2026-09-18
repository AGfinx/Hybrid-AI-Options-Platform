"use client";

import React, { useState, useEffect } from "react";
import Navbar from "@/components/Navbar";
import CockpitView from "@/components/CockpitView";
import SurfaceView from "@/components/SurfaceView";
import RecommendationsView from "@/components/RecommendationsView";
import MandatesView from "@/components/MandatesView";
import PaperTradingView from "@/components/PaperTradingView";
import RiskView from "@/components/RiskView";
import AuditView from "@/components/AuditView";
import ReviewModal from "@/components/ReviewModal";
import EmergencyStopModal from "@/components/EmergencyStopModal";
import { api } from "@/lib/api";

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<string>("cockpit");
  const [mode, setMode] = useState<string>("recommendation");
  const [marketHealth, setMarketHealth] = useState<any>(null);
  const [surfaceData, setSurfaceData] = useState<any>(null);
  const [surfaceAsset, setSurfaceAsset] = useState<string>("BTC");
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [mandates, setMandates] = useState<any[]>([]);
  const [portfolioRisk, setPortfolioRisk] = useState<any>(null);
  const [orders, setOrders] = useState<any[]>([]);
  const [positions, setPositions] = useState<any[]>([]);
  const [pnlReport, setPnlReport] = useState<any>(null);
  const [auditEvents, setAuditEvents] = useState<any[]>([]);

  const [activeReviewRec, setActiveReviewRec] = useState<any>(null);
  const [showEmergencyModal, setShowEmergencyModal] = useState<boolean>(false);
  const [isReplaying, setIsReplaying] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);

  // Initial Data Load
  const loadAllData = async (asset = surfaceAsset) => {
    try {
      const [
        modeRes,
        healthRes,
        surfaceRes,
        recsRes,
        mandatesRes,
        riskRes,
        ordersRes,
        posRes,
        pnlRes,
        auditRes,
      ] = await Promise.allSettled([
        api.getOperatingMode(),
        api.getMarketHealth(),
        api.getSurface(asset),
        api.getRecommendations(),
        api.getMandates(),
        api.getPortfolioRisk(),
        api.getPaperOrders(),
        api.getPaperPositions(),
        api.getPnLReport(),
        api.getAuditEvents(),
      ]);

      if (modeRes.status === "fulfilled") setMode(modeRes.value.operating_mode);
      if (healthRes.status === "fulfilled") setMarketHealth(healthRes.value);
      if (surfaceRes.status === "fulfilled") setSurfaceData(surfaceRes.value);
      if (recsRes.status === "fulfilled") setRecommendations(recsRes.value);
      if (mandatesRes.status === "fulfilled") setMandates(mandatesRes.value);
      if (riskRes.status === "fulfilled") setPortfolioRisk(riskRes.value);
      if (ordersRes.status === "fulfilled") setOrders(ordersRes.value);
      if (posRes.status === "fulfilled") setPositions(posRes.value);
      if (pnlRes.status === "fulfilled") setPnlReport(pnlRes.value);
      if (auditRes.status === "fulfilled") setAuditEvents(auditRes.value);
    } catch (e) {
      console.error("Error loading dashboard data:", e);
    }
  };

  useEffect(() => {
    loadAllData();
    const interval = setInterval(() => {
      loadAllData();
    }, 10000);
    return () => clearInterval(interval);
  }, [surfaceAsset]);

  const handleAssetChange = async (asset: string) => {
    setSurfaceAsset(asset);
    try {
      const surf = await api.getSurface(asset);
      setSurfaceData(surf);
    } catch (e) {
      console.error(`Failed to load ${asset} surface:`, e);
    }
  };

  const handleModeChange = async (newMode: string) => {
    try {
      await api.switchOperatingMode(newMode, "User mode selector change");
      setMode(newMode);
      loadAllData();
    } catch (e: any) {
      alert(`Could not switch mode: ${e.message}`);
    }
  };

  const handleReplayTick = async () => {
    setIsReplaying(true);
    try {
      await api.replayTick(10);
      await loadAllData();
    } catch (e) {
      console.error("Replay tick error:", e);
    } finally {
      setIsReplaying(false);
    }
  };

  const handleGenerateRecs = async (underlying?: string) => {
    setIsGenerating(true);
    try {
      await api.generateRecommendations(underlying);
      await loadAllData();
      setActiveTab("recommendations");
    } catch (e) {
      console.error("Opportunity generation error:", e);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRejectRec = async (rec: any, reason: string) => {
    try {
      await api.rejectRecommendation(rec.id, reason);
      loadAllData();
    } catch (e: any) {
      alert(`Reject failed: ${e.message}`);
    }
  };

  const handleConfirmEmergencyStop = async (reason: string) => {
    try {
      await api.triggerEmergencyStop(reason);
      setShowEmergencyModal(false);
      loadAllData();
    } catch (e: any) {
      alert(`Emergency Stop failed: ${e.message}`);
    }
  };

  const handleResetEmergencyStop = async () => {
    try {
      await api.resetEmergencyStop();
      loadAllData();
    } catch (e: any) {
      alert(`Reset failed: ${e.message}`);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0e17] text-slate-100 flex flex-col">
      {/* Top Navbar */}
      <Navbar
        mode={mode}
        onModeChange={handleModeChange}
        marketHealth={marketHealth}
        onReplayTick={handleReplayTick}
        onGenerateRecs={() => handleGenerateRecs()}
        onEmergencyStopClick={() => setShowEmergencyModal(true)}
        isReplaying={isReplaying}
        isGenerating={isGenerating}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      {/* Main View Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6">
        {activeTab === "cockpit" && (
          <CockpitView
            portfolioRisk={portfolioRisk}
            recommendations={recommendations}
            pnlReport={pnlReport}
            marketHealth={marketHealth}
            onOpenReview={(rec) => setActiveReviewRec(rec)}
            onGenerateRecs={() => handleGenerateRecs()}
            onRefresh={() => loadAllData()}
          />
        )}

        {activeTab === "surface" && (
          <SurfaceView
            surfaceData={surfaceData}
            onRefresh={() => loadAllData()}
            underlying={surfaceAsset}
            onSelectUnderlying={handleAssetChange}
          />
        )}

        {activeTab === "recommendations" && (
          <RecommendationsView
            recommendations={recommendations}
            onOpenReview={(rec) => setActiveReviewRec(rec)}
            onReject={handleRejectRec}
            onGenerateRecs={handleGenerateRecs}
            onToggleWatchlist={() => loadAllData()}
          />
        )}

        {activeTab === "mandates" && (
          <MandatesView
            mandates={mandates}
            onRefresh={() => loadAllData()}
          />
        )}

        {activeTab === "paper" && (
          <PaperTradingView
            orders={orders}
            positions={positions}
            pnlReport={pnlReport}
            onRefresh={() => loadAllData()}
          />
        )}

        {activeTab === "risk" && (
          <RiskView
            portfolioRisk={portfolioRisk}
            onRefresh={() => loadAllData()}
            onEmergencyStop={() => setShowEmergencyModal(true)}
            onResetEmergencyStop={handleResetEmergencyStop}
          />
        )}

        {activeTab === "audit" && (
          <AuditView
            auditEvents={auditEvents}
            onRefresh={() => loadAllData()}
          />
        )}
      </main>

      {/* Review & Edit Modal */}
      {activeReviewRec && (
        <ReviewModal
          rec={activeReviewRec}
          onClose={() => setActiveReviewRec(null)}
          onApproved={() => loadAllData()}
        />
      )}

      {/* Emergency Stop Modal */}
      {showEmergencyModal && (
        <EmergencyStopModal
          onClose={() => setShowEmergencyModal(false)}
          onConfirm={handleConfirmEmergencyStop}
        />
      )}

      {/* Footer Info */}
      <footer className="border-t border-slate-900 py-3 px-6 text-center text-slate-600 text-xs font-mono-num">
        Hybrid AI Options Platform • Milestone 2 Multi-Asset & Multi-Leg Architecture • Deribit Public Market Data • Live Order Routing Strictly Disabled
      </footer>
    </div>
  );
}
