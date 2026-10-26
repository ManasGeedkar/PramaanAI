import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { EvaluationResult } from '../api/types';
import {
  CheckCircle2,
  XCircle,
  RefreshCw,
  Award,
  ShieldCheck,
  Zap,
  Target,
  FileCheck2,
  Building2,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
} from 'lucide-react';

export const EvaluationPage: React.FC = () => {
  const [evalData, setEvalData] = useState<EvaluationResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [filterText, setFilterText] = useState<string>('');
  const [expandedInst, setExpandedInst] = useState<string | null>(null);

  const fetchEval = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getEvaluation();
      setEvalData(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to compute benchmark evaluation metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEval();
  }, []);

  const filteredApps = (evalData?.applications || []).filter((app) => {
    if (!filterText) return true;
    const q = filterText.toLowerCase();
    return (
      app.institution_id.toLowerCase().includes(q) ||
      (app.application_no || '').toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-5">
      {/* Page Header */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Synthetic Benchmark Evaluation
            </h1>
            <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-mono text-xs font-bold border border-emerald-200">
              Ground Truth Verified
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl">
            Automated performance evaluation comparing extraction values, mock registry verifications, advisory findings, and triage risk bands against curated AICTE synthetic ground truth labels (<code className="font-mono text-[11px] text-slate-700">data/labels/</code>).
          </p>
        </div>

        <button
          onClick={fetchEval}
          disabled={loading}
          className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-blue-900 hover:bg-blue-800 rounded-lg shadow-xs transition-colors flex-shrink-0"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>{loading ? 'Evaluating...' : 'Re-compute Metrics'}</span>
        </button>
      </div>

      {/* Loading State */}
      {loading && !evalData && (
        <div className="p-16 bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center text-slate-500 gap-3">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-900" />
          <div className="text-sm font-semibold text-slate-800">
            Running Automated Ground Truth Evaluation...
          </div>
          <div className="text-xs text-slate-400">
            Comparing extracted bounding boxes and findings across synthetic applications.
          </div>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="p-6 bg-red-50 border border-red-300 rounded-xl text-red-900 space-y-2">
          <div className="flex items-center gap-2 font-bold text-sm">
            <AlertTriangle className="w-5 h-5 text-red-600" />
            <span>Benchmark Evaluation Error</span>
          </div>
          <p className="text-xs text-red-800">{error}</p>
          <button
            onClick={fetchEval}
            className="mt-2 px-3 py-1.5 bg-red-700 text-white rounded text-xs font-semibold hover:bg-red-800"
          >
            Retry Evaluation
          </button>
        </div>
      )}

      {/* Evaluated Metrics */}
      {evalData && (
        <>
          {/* KPI Cards Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs hover:border-slate-300 transition-colors">
              <div className="flex items-center justify-between text-slate-500 mb-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider">Field Extraction</span>
                <FileCheck2 className="w-4 h-4 text-primary-700" />
              </div>
              <div className="text-2xl font-bold text-slate-900 font-mono tracking-tight">
                {evalData.extraction_accuracy}%
              </div>
              <span className="text-[10px] text-emerald-600 font-semibold flex items-center gap-1 mt-0.5">
                <CheckCircle2 className="w-3 h-3" /> Text layer + RapidOCR
              </span>
            </div>

            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs hover:border-slate-300 transition-colors">
              <div className="flex items-center justify-between text-slate-500 mb-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider">Registry Verification</span>
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="text-2xl font-bold text-emerald-700 font-mono tracking-tight">
                {evalData.verification_accuracy}%
              </div>
              <span className="text-[10px] text-slate-500 mt-0.5 block">
                All 6 verification statuses
              </span>
            </div>

            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs hover:border-slate-300 transition-colors">
              <div className="flex items-center justify-between text-slate-500 mb-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider">Finding Recall</span>
                <Target className="w-4 h-4 text-blue-700" />
              </div>
              <div className="text-2xl font-bold text-blue-900 font-mono tracking-tight">
                {evalData.finding_recall}%
              </div>
              <span className="text-[10px] text-slate-500 mt-0.5 block">
                {evalData.matched_findings_count} of {evalData.total_expected_findings} expected found
              </span>
            </div>

            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs hover:border-slate-300 transition-colors">
              <div className="flex items-center justify-between text-slate-500 mb-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider">Risk Band Accuracy</span>
                <Award className="w-4 h-4 text-amber-600" />
              </div>
              <div className="text-2xl font-bold text-emerald-700 font-mono tracking-tight">
                {evalData.risk_band_accuracy}%
              </div>
              <span className="text-[10px] text-slate-500 mt-0.5 block">
                Triage band alignment
              </span>
            </div>

            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs hover:border-slate-300 transition-colors">
              <div className="flex items-center justify-between text-slate-500 mb-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider">Scrutiny Latency</span>
                <Zap className="w-4 h-4 text-purple-600" />
              </div>
              <div className="text-2xl font-bold text-purple-900 font-mono tracking-tight">
                {evalData.average_pipeline_seconds}s
              </div>
              <span className="text-[10px] text-slate-500 mt-0.5 block">
                Per complete application dossier
              </span>
            </div>
          </div>

          {/* Table Container */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
            {/* Table Header Toolbar */}
            <div className="p-4 border-b border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-3 bg-slate-50/70">
              <div>
                <h2 className="text-sm font-bold text-slate-900">
                  Per-Application Expected vs. Found Findings Matrix
                </h2>
                <div className="flex flex-wrap items-center gap-3 mt-1.5 text-[11px]">
                  <span className="flex items-center gap-1 text-emerald-800 font-semibold">
                    <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                    Green = Found in Ground Truth
                  </span>
                  <span className="flex items-center gap-1 text-red-800 font-semibold">
                    <span className="w-2 h-2 rounded-full bg-red-500"></span>
                    Red = Missed (False Negative)
                  </span>
                  <span className="flex items-center gap-1 text-slate-600 font-semibold">
                    <span className="w-2 h-2 rounded-full bg-slate-400"></span>
                    Grey = Extra / Expected Behaviour (Unreadable Document Flagged)
                  </span>
                </div>
              </div>

              {/* Filter Input */}
              <input
                type="text"
                placeholder="Filter institution (e.g. INST04)..."
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
                className="px-3 py-1.5 text-xs border border-slate-300 rounded-lg bg-white focus:ring-1 focus:ring-blue-500 w-full md:w-64"
              />
            </div>

            {/* Application Comparison Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-100/70 border-b border-slate-200 text-slate-600 text-[10px] uppercase font-bold tracking-wider">
                    <th className="py-3 px-4 w-10"></th>
                    <th className="py-3 px-4">Application</th>
                    <th className="py-3 px-4">Triage Risk Band</th>
                    <th className="py-3 px-4">Recall</th>
                    <th className="py-3 px-4">Ground Truth Expected Findings</th>
                    <th className="py-3 px-4">Extra / Diagnostic Flags</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredApps.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-slate-400 text-xs">
                        No applications match the search query.
                      </td>
                    </tr>
                  ) : (
                    filteredApps.map((row) => {
                      const isExpanded = expandedInst === row.institution_id;
                      const isBandMatch = row.risk_band_matched;
                      const expectedFindings = row.expected_findings || [];
                      const extraFindings = row.extra_findings || [];

                      return (
                        <React.Fragment key={row.institution_id}>
                          <tr
                            onClick={() => setExpandedInst(isExpanded ? null : row.institution_id)}
                            className={`hover:bg-slate-50/80 cursor-pointer transition-colors ${
                              isExpanded ? 'bg-blue-50/30' : ''
                            }`}
                          >
                            <td className="py-3 px-3 text-slate-400">
                              {isExpanded ? (
                                <ChevronDown className="w-4 h-4 text-blue-900" />
                              ) : (
                                <ChevronRight className="w-4 h-4" />
                              )}
                            </td>

                            <td className="py-3 px-4 font-bold text-slate-900 whitespace-nowrap">
                              <div className="flex items-center gap-1.5">
                                <Building2 className="w-3.5 h-3.5 text-slate-500" />
                                <span>{row.institution_id}</span>
                              </div>
                              <div className="text-[10px] text-slate-400 font-mono font-normal">
                                {row.application_no}
                              </div>
                            </td>

                            <td className="py-3 px-4 whitespace-nowrap">
                              <div className="flex items-center gap-1.5">
                                <span
                                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                    row.actual_risk_band === 'High'
                                      ? 'bg-red-100 text-red-800 border border-red-200'
                                      : row.actual_risk_band === 'Medium'
                                      ? 'bg-amber-100 text-amber-800 border border-amber-200'
                                      : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                                  }`}
                                >
                                  {row.actual_risk_band}
                                </span>
                                {isBandMatch ? (
                                  <span className="text-[10px] text-emerald-700 font-semibold flex items-center gap-0.5" title="Matches ground truth risk band">
                                    <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                                    <span>Match</span>
                                  </span>
                                ) : (
                                  <span className="text-[10px] text-amber-700 font-semibold" title={`Expected ${row.expected_risk_band}`}>
                                    Expected: {row.expected_risk_band}
                                  </span>
                                )}
                              </div>
                              <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                                {row.risk_score} risk pts
                              </div>
                            </td>

                            <td className="py-3 px-4 whitespace-nowrap">
                              <div className="font-mono font-bold text-slate-800 text-xs">
                                {row.matched_count}/{row.total_expected}
                              </div>
                              <div className="text-[10px] text-slate-400">
                                {row.total_expected > 0
                                  ? `${Math.round((row.matched_count / row.total_expected) * 100)}% recall`
                                  : 'Clean dossier'}
                              </div>
                            </td>

                            {/* Expected Findings Chips: Green = Found, Red = Missed */}
                            <td className="py-3 px-4">
                              <div className="flex flex-wrap gap-1.5 max-w-md">
                                {expectedFindings.length === 0 ? (
                                  <span className="text-slate-400 italic text-[11px]">
                                    None expected (baseline compliant)
                                  </span>
                                ) : (
                                  expectedFindings.map((ef: any, idx: number) => {
                                    const isFound = ef.status === 'found';
                                    const code = ef.expected?.code || 'FINDING';
                                    const docType = ef.expected?.doc_type;
                                    const ruleId = ef.expected?.rule_id;

                                    return (
                                      <span
                                        key={idx}
                                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold border ${
                                          isFound
                                            ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                                            : 'bg-red-50 text-red-800 border-red-300'
                                        }`}
                                        title={`${code} ${docType ? `(${docType})` : ''} ${ruleId ? `[${ruleId}]` : ''}`}
                                      >
                                        {isFound ? (
                                          <CheckCircle2 className="w-3 h-3 text-emerald-600 flex-shrink-0" />
                                        ) : (
                                          <XCircle className="w-3 h-3 text-red-600 flex-shrink-0" />
                                        )}
                                        <span>{code}</span>
                                        {ruleId && <span className="opacity-75">[{ruleId}]</span>}
                                      </span>
                                    );
                                  })
                                )}
                              </div>
                            </td>

                            {/* Extra Findings & Diagnostic Flags: Grey = Extra / Expected Behaviour */}
                            <td className="py-3 px-4">
                              <div className="flex flex-wrap gap-1.5 max-w-sm">
                                {extraFindings.length === 0 ? (
                                  <span className="text-slate-400 italic text-[11px]">—</span>
                                ) : (
                                  extraFindings.map((xf: any, idx: number) => {
                                    const isExpectedUnreadable =
                                      xf.is_expected_unreadable ||
                                      xf.code === 'LOW_QUALITY_SCAN' ||
                                      xf.code === 'LOW_OCR_CONFIDENCE';

                                    return (
                                      <span
                                        key={idx}
                                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-slate-100 text-slate-700 border border-slate-300"
                                        title={xf.title || xf.code}
                                      >
                                        <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span>
                                        <span>{xf.code}</span>
                                        {isExpectedUnreadable ? (
                                          <span className="text-[9px] font-sans font-normal text-slate-500 italic">
                                            (expected behaviour)
                                          </span>
                                        ) : (
                                          <span className="text-[9px] font-sans font-normal text-slate-400">
                                            (extra)
                                          </span>
                                        )}
                                      </span>
                                    );
                                  })
                                )}
                              </div>
                            </td>
                          </tr>

                          {/* Expandable row showing full dossier verification summary */}
                          {isExpanded && (
                            <tr className="bg-slate-50/90">
                              <td colSpan={6} className="px-6 py-4 border-b border-slate-200">
                                <div className="space-y-3">
                                  <div className="font-bold text-xs text-slate-800">
                                    Detailed Findings Breakdown for {row.institution_id} ({row.application_no}):
                                  </div>

                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                                    <div className="bg-white p-3 rounded-lg border border-slate-200">
                                      <div className="font-semibold text-slate-700 mb-2 flex items-center justify-between">
                                        <span>Expected Findings Checklist ({expectedFindings.length})</span>
                                        <span className="text-[10px] text-slate-400">Ground Truth</span>
                                      </div>
                                      <ul className="space-y-1.5">
                                        {expectedFindings.map((ef: any, i: number) => (
                                          <li
                                            key={i}
                                            className={`p-2 rounded border text-[11px] flex items-start gap-2 ${
                                              ef.status === 'found'
                                                ? 'bg-emerald-50/60 border-emerald-200 text-emerald-950'
                                                : 'bg-red-50/60 border-red-200 text-red-950'
                                            }`}
                                          >
                                            {ef.status === 'found' ? (
                                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0 mt-0.5" />
                                            ) : (
                                              <XCircle className="w-3.5 h-3.5 text-red-600 flex-shrink-0 mt-0.5" />
                                            )}
                                            <div>
                                              <div className="font-mono font-bold">
                                                {ef.expected?.code} {ef.expected?.rule_id ? `[${ef.expected?.rule_id}]` : ''}
                                              </div>
                                              <div className="text-[10px] opacity-80 mt-0.5">
                                                Document: {ef.expected?.doc_type || 'General'} • Status: {ef.status.toUpperCase()}
                                              </div>
                                            </div>
                                          </li>
                                        ))}
                                      </ul>
                                    </div>

                                    <div className="bg-white p-3 rounded-lg border border-slate-200">
                                      <div className="font-semibold text-slate-700 mb-2 flex items-center justify-between">
                                        <span>System Diagnostic &amp; Quality Flags ({extraFindings.length})</span>
                                        <span className="text-[10px] text-slate-400">Scrutiny Engine</span>
                                      </div>
                                      {extraFindings.length === 0 ? (
                                        <div className="text-slate-400 italic text-[11px] p-2">
                                          No additional diagnostic findings or quality flags raised.
                                        </div>
                                      ) : (
                                        <ul className="space-y-1.5">
                                          {extraFindings.map((xf: any, i: number) => {
                                            const isExpUnread =
                                              xf.is_expected_unreadable ||
                                              xf.code === 'LOW_QUALITY_SCAN' ||
                                              xf.code === 'LOW_OCR_CONFIDENCE';
                                            return (
                                              <li
                                                key={i}
                                                className="p-2 rounded border border-slate-200 bg-slate-50 text-[11px] text-slate-800"
                                              >
                                                <div className="font-mono font-bold flex items-center justify-between">
                                                  <span>{xf.code}</span>
                                                  <span className="text-[9px] uppercase font-bold text-slate-500 bg-slate-200 px-1 py-0.2 rounded">
                                                    {xf.severity}
                                                  </span>
                                                </div>
                                                <div className="text-[10px] text-slate-500 mt-0.5">
                                                  {xf.title || 'Diagnostic finding'}
                                                </div>
                                                {isExpUnread && (
                                                  <div className="mt-1 text-[10px] font-semibold text-slate-600">
                                                    ℹ Note: expected behaviour (unreadable document flagged for manual officer scrutiny).
                                                  </div>
                                                )}
                                              </li>
                                            );
                                          })}
                                        </ul>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Advisory Footer */}
      <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-center text-xs text-slate-500">
        AI findings are advisory. Final decisions rest with competent AICTE authorities.
      </div>
    </div>
  );
};
