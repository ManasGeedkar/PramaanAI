import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { AuditLogItem, AuditVerifyResult } from '../api/types';
import {
  ShieldCheck,
  ShieldAlert,
  RefreshCw,
  KeyRound,
  Filter,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { formatDateTime } from '../utils/date';

export const AuditLogPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [verifyResult, setVerifyResult] = useState<AuditVerifyResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [verifying, setVerifying] = useState<boolean>(false);
  const [selectedApp, setSelectedApp] = useState<string>('all');
  const [applications, setApplications] = useState<Array<{ id: number; application_no: string; institution_id: string }>>([]);
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);

  const fetchApps = async () => {
    try {
      const apps = await api.getApplications('risk');
      const mapped = apps.map((a) => ({
        id: a.id,
        application_no: a.application_no || a.no || `APP-${a.id}`,
        institution_id: a.institution_id || `INST-${a.id}`,
      }));
      setApplications(mapped);
    } catch {
      // fallback
    }
  };

  const fetchLogs = async (appId?: string) => {
    try {
      setLoading(true);
      const targetApp = appId !== undefined ? appId : selectedApp;
      const data = await api.getAuditLogs(undefined, targetApp);
      setLogs(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyChain = async () => {
    try {
      setVerifying(true);
      const res = await api.verifyAuditChain();
      setVerifyResult(res);
    } catch (err: any) {
      alert(`Verification error: ${err.message}`);
    } finally {
      setVerifying(false);
    }
  };

  const handleAppChange = (val: string) => {
    setSelectedApp(val);
    fetchLogs(val);
  };

  useEffect(() => {
    fetchApps();
    fetchLogs('all');
  }, []);

  return (
    <div className="space-y-4">
      {/* Header bar */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Cryptographic Audit Log
            </h1>
            <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-xs font-semibold">
              SHA-256 Hash Chaining
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl">
            Append-only, tamper-evident audit trail capturing every system pipeline stage, registry query, and human review decision with cryptographic parent-hash linkage.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {verifyResult && (
            <div
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border ${
                verifyResult.ok
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                  : 'bg-red-50 text-red-800 border-red-300'
              }`}
            >
              {verifyResult.ok ? (
                <>
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span>Chain Intact</span>
                </>
              ) : (
                <>
                  <ShieldAlert className="w-4 h-4 text-red-600" />
                  <span>Chain Broken at #{verifyResult.broken_at}</span>
                </>
              )}
            </div>
          )}

          <button
            onClick={handleVerifyChain}
            disabled={verifying}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-blue-900 hover:bg-blue-800 rounded-lg shadow-xs transition-all"
          >
            <KeyRound className={`w-3.5 h-3.5 ${verifying ? 'animate-spin' : ''}`} />
            <span>Verify Chain</span>
          </button>

          <button
            onClick={() => fetchLogs()}
            disabled={loading}
            className="p-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg border border-slate-200"
            title="Refresh logs"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white p-3 rounded-lg border border-slate-200 flex items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-500" />
          <span className="font-semibold text-slate-700">Filter by Application:</span>
          <select
            value={selectedApp}
            onChange={(e) => handleAppChange(e.target.value)}
            className="px-2.5 py-1 border border-slate-300 rounded-md bg-white text-slate-800 font-medium focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">All Applications &amp; System Events</option>
            {applications.map((app) => (
              <option key={app.id} value={app.institution_id}>
                {app.institution_id} — {app.application_no}
              </option>
            ))}
          </select>
        </div>

        <div className="text-slate-500 text-[11px]">
          Showing <strong>{logs.length}</strong> logged entries
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
        {loading && logs.length === 0 ? (
          <div className="p-12 text-center text-slate-400 text-sm">Loading audit chain...</div>
        ) : (
          <div className="overflow-x-auto max-h-[700px]">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="sticky top-0 bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[10px] tracking-wider z-10">
                <tr>
                  <th className="py-2.5 px-3 w-10"></th>
                  <th className="py-2.5 px-3">#ID</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Actor</th>
                  <th className="py-2.5 px-3">Action</th>
                  <th className="py-2.5 px-3">Entity</th>
                  <th className="py-2.5 px-3">SHA-256 Hash</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                {logs.map((log) => {
                  const isExpanded = expandedLogId === log.id;
                  let parsedPayload: any = null;
                  try {
                    parsedPayload = log.payload_json ? JSON.parse(log.payload_json) : null;
                  } catch {
                    parsedPayload = log.payload_json;
                  }

                  return (
                    <React.Fragment key={log.id}>
                      <tr
                        onClick={() => setExpandedLogId(isExpanded ? null : log.id)}
                        className={`hover:bg-slate-50/80 cursor-pointer transition-colors ${
                          isExpanded ? 'bg-blue-50/40' : ''
                        }`}
                      >
                        <td className="py-2 px-3 text-slate-400">
                          {isExpanded ? (
                            <ChevronDown className="w-3.5 h-3.5 text-blue-900" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5" />
                          )}
                        </td>
                        <td className="py-2 px-3 text-slate-400 font-bold">#{log.id}</td>
                        <td className="py-2 px-3 text-slate-600 whitespace-nowrap">
                          {formatDateTime(log.ts)}
                        </td>
                        <td className="py-2 px-3">
                          <span
                            className={`px-1.5 py-0.5 rounded font-sans font-medium text-[10px] ${
                              log.actor === 'officer'
                                ? 'bg-amber-100 text-amber-900'
                                : log.actor === 'pipeline' || log.actor === 'system'
                                ? 'bg-slate-100 text-slate-700'
                                : 'bg-blue-100 text-blue-800'
                            }`}
                          >
                            {log.actor}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-blue-900 font-bold">{log.action}</td>
                        <td className="py-2 px-3 text-slate-700">
                          {log.entity_type}:{log.entity_id}
                        </td>
                        <td className="py-2 px-3 text-slate-500 font-mono text-[10px]" title={log.hash}>
                          {log.hash ? log.hash.slice(0, 16) + '...' : ''}
                        </td>
                      </tr>

                      {/* Expandable row showing payload and hashes */}
                      {isExpanded && (
                        <tr className="bg-slate-50/80">
                          <td colSpan={7} className="px-6 py-3 border-b border-slate-200">
                            <div className="space-y-2 text-xs">
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
                                <div>
                                  <span className="text-slate-400 block">Previous Hash (Parent):</span>
                                  <span className="font-mono text-slate-700 break-all select-all">
                                    {log.prev_hash || '(genesis block)'}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-slate-400 block">Current Block Hash:</span>
                                  <span className="font-mono text-blue-900 font-bold break-all select-all">
                                    {log.hash}
                                  </span>
                                </div>
                              </div>

                              {parsedPayload && (
                                <div className="mt-2">
                                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">
                                    Payload Details:
                                  </span>
                                  <pre className="mt-1 p-2 bg-slate-900 text-slate-200 rounded text-[11px] overflow-x-auto">
                                    {typeof parsedPayload === 'object'
                                      ? JSON.stringify(parsedPayload, null, 2)
                                      : parsedPayload}
                                  </pre>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Advisory Footer */}
      <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-center text-xs text-slate-500">
        AI findings are advisory. Final decisions rest with competent AICTE authorities.
      </div>
    </div>
  );
};
