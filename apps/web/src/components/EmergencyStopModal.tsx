"use client";

import React, { useState } from "react";
import { ShieldAlert, AlertTriangle, X } from "lucide-react";

interface EmergencyStopModalProps {
  onClose: () => void;
  onConfirm: (reason: string) => void;
}

export default function EmergencyStopModal({ onClose, onConfirm }: EmergencyStopModalProps) {
  const [reason, setReason] = useState<string>("Manual operator stop: unexpected market volatility or risk review");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) return;
    setIsSubmitting(true);
    onConfirm(reason.trim());
  };

  return (
    <div className="fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 z-50">
      <div className="bg-[#180f14] border border-rose-600 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl shadow-rose-950/50">
        <div className="flex items-start justify-between border-b border-rose-900/60 pb-3">
          <div className="flex items-center gap-2.5 text-rose-400">
            <ShieldAlert className="h-6 w-6 shrink-0 animate-pulse" />
            <div>
              <h2 className="text-lg font-bold text-slate-100">CONFIRM EMERGENCY STOP</h2>
              <span className="text-[11px] text-rose-300">Circuit Breaker Fail-Closed Override</span>
            </div>
          </div>

          <button onClick={onClose} className="p-1 rounded hover:bg-rose-950 text-rose-300">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-3.5 rounded-lg bg-rose-950/40 border border-rose-900/80 text-rose-200 text-xs space-y-2">
          <p className="font-semibold">By engaging the Emergency Stop:</p>
          <ul className="list-disc pl-4 space-y-1 text-rose-300">
            <li>All new paper order submissions will be <strong>immediately blocked</strong>.</li>
            <li>No pending recommendations can be approved until manual reset.</li>
            <li>An immutable high-priority audit entry will be dispatched.</li>
          </ul>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1 text-xs">
            <label className="text-slate-300 font-medium">Mandatory Incident Reason:</label>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
              className="w-full p-2.5 rounded bg-slate-950 border border-rose-800/80 text-slate-100 text-xs focus:outline-none focus:border-rose-500"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-2 border-t border-rose-900/60">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isSubmitting || !reason.trim()}
              className="px-5 py-2 rounded-md bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-600/40 flex items-center gap-1.5 transition"
            >
              <ShieldAlert className="h-4 w-4" />
              <span>ENGAGE EMERGENCY STOP</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
