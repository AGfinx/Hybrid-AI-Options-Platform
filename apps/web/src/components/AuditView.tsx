"use client";

import React, { useState } from "react";
import { Shield, Clock, Search, RefreshCw, ChevronDown, ChevronRight } from "lucide-react";

interface AuditViewProps {
  auditEvents: any[];
  onRefresh: () => void;
}

export default function AuditView({ auditEvents, onRefresh }: AuditViewProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filtered = (auditEvents || []).filter((e) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      e.action?.toLowerCase().includes(term) ||
      e.actor_id?.toLowerCase().includes(term) ||
      e.object_type?.toLowerCase().includes(term) ||
      e.request_id?.toLowerCase().includes(term)
    );
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass-panel p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-100">Immutable Audit Trail & Compliance Log</h2>
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-800 text-slate-300 border border-slate-700 uppercase">
              WORM Log
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Every human approval, rejection rationale, risk exception, model version reference, and parameter mutation is recorded.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search action, actor, request ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8 pr-3 py-1.5 rounded-md bg-slate-900 border border-slate-700 text-slate-200 text-xs w-64 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <button
            onClick={onRefresh}
            className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs border border-slate-700 transition flex items-center gap-1.5"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Events Table */}
      <div className="glass-panel p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 className="font-bold text-slate-100 text-base">Recorded Audit Events</h3>
          <span className="text-xs font-mono-num text-slate-400">{filtered.length} Events</span>
        </div>

        {filtered.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-sm">
            No audit records match the search filter.
          </div>
        ) : (
          <div className="space-y-2 font-mono-num text-xs">
            {filtered.map((e) => {
              const isExpanded = expandedId === e.id;
              return (
                <div
                  key={e.id}
                  className="p-3 rounded-lg bg-slate-900/60 border border-slate-800/80 hover:border-slate-700 transition space-y-2"
                >
                  <div
                    onClick={() => setExpandedId(isExpanded ? null : e.id)}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-cyan-400" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-slate-500" />
                      )}
                      <span className="px-2 py-0.5 rounded text-[10px] uppercase font-bold bg-cyan-950 text-cyan-300 border border-cyan-800">
                        {e.action}
                      </span>
                      <span className="text-slate-300 font-semibold">{e.object_type}</span>
                      {e.object_id && (
                        <span className="text-slate-500 text-[11px]">({e.object_id})</span>
                      )}
                    </div>

                    <div className="flex items-center gap-4 text-slate-400 text-[11px]">
                      <span>Actor: <strong className="text-slate-200">{e.actor_id}</strong></span>
                      <span>Req: <strong className="text-cyan-400">{e.request_id}</strong></span>
                      <span>{new Date(e.timestamp).toLocaleTimeString()}</span>
                    </div>
                  </div>

                  {/* Expanded Diff Payload */}
                  {isExpanded && (
                    <div className="pt-2 border-t border-slate-800 grid grid-cols-1 sm:grid-cols-2 gap-3 text-[11px]">
                      <div className="bg-slate-950 p-2.5 rounded border border-slate-800/80">
                        <span className="text-slate-500 block mb-1">BEFORE STATE</span>
                        <pre className="text-rose-300 overflow-x-auto whitespace-pre-wrap">
                          {e.before_state ? JSON.stringify(e.before_state, null, 2) : "null"}
                        </pre>
                      </div>
                      <div className="bg-slate-950 p-2.5 rounded border border-slate-800/80">
                        <span className="text-slate-500 block mb-1">AFTER STATE</span>
                        <pre className="text-emerald-300 overflow-x-auto whitespace-pre-wrap">
                          {e.after_state ? JSON.stringify(e.after_state, null, 2) : "null"}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
