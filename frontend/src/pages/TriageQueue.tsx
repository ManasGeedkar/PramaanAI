import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { ApplicationQueueItem } from '../api/types';
import {
  AlertTriangle,
  AlertCircle,
  Info,
  ChevronRight,
  Search,
  RefreshCw,
  FileText,
} from 'lucide-react';
import { formatDate } from '../utils/date';

interface TriageQueueProps {
  onSelectApplication: (id: number) => void;
}

export const TriageQueue: React.FC<TriageQueueProps> = ({ onSelectApplication }) => {
  const [applications, setApplications] = useState<ApplicationQueueItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [bandFilter, setBandFilter] = useState<string>('all');
  const [reRunningId, setReRunningId] = useState<number | null>(null);

  const fetchQueue = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getApplications('risk');
      setApplications(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load application queue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, []);

  const handleReRun = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      setReRunningId(id);
      await api.runApplicationPipeline(id);
      await fetchQueue();
    } catch (err: any) {
      alert(`Re-run failed: ${err.message}`);
    } finally {
      setReRunningId(null);
    }
  };

  const filteredApps = applications.filter((app) => {
    const instName = app.institution_name || app.institution || '';
    const instId = app.institution_id || '';
    const appNo = app.application_no || app.no || '';

    const matchesSearch =
      instName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      instId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      appNo.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesBand = bandFilter === 'all' || app.risk_band === bandFilter;

    return matchesSearch && matchesBand;
  });

  const getCategoryLabel = (category: string) => {
    if (category === 'EoA') return 'EoA';
    if (category === 'EoA_INTAKE_INCREASE') return 'EoA + Intake increase';
    return category ? category.replace(/_/g, ' ') : '';
  };

  const getRiskBandBadge = (band: string, score: number, breakdown?: any[], rowIndex: number = 0) => {
    const bandConfig = {
      High: {
        bg: 'bg-red-50 text-red-700 border-red-200 hover:bg-red-100',
        dot: 'bg-red-500',
      },
      Medium: {
        bg: 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100',
        dot: 'bg-amber-500',
      },
      Low: {
        bg: 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100',
        dot: 'bg-emerald-500',
      },
    }[band] || {
      bg: 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100',
      dot: 'bg-slate-400',
    };

    // Open popover below badge when there isn't room above (first 3 rows)
    const popoverPosition = rowIndex < 3 ? 'top-full mt-2' : 'bottom-full mb-2';

    return (
      <div className="relative group inline-block">
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border transition-colors cursor-help ${bandConfig.bg}`}
        >
          <span className={`w-2 h-2 rounded-full ${bandConfig.dot}`} />
          {band} ({score} pts)
        </span>

        {/* Hover Risk Breakdown Popover */}
        {breakdown && breakdown.length > 0 && (
          <div
            className={`absolute left-1/2 -translate-x-1/2 ${popoverPosition} hidden group-hover:block z-50 w-72 p-3 bg-slate-900 text-white text-xs rounded-lg shadow-xl border border-slate-700 pointer-events-none text-left`}
          >
            <div className="font-semibold text-slate-200 pb-1.5 mb-1.5 border-b border-slate-700 flex justify-between">
              <span>Risk Score Breakdown</span>
              <span className="font-mono text-emerald-400">{score} pts total</span>
            </div>
            <ul className="space-y-1.5 max-h-48 overflow-y-auto">
              {breakdown.map((item, i) => (
                <li key={i} className="flex justify-between items-start gap-2 text-[11px]">
                  <span className="text-slate-300 leading-tight">{item.reason}</span>
                  <span className="font-mono font-bold text-amber-400 flex-shrink-0">
                    +{item.points}
                  </span>
                </li>
              ))}
            </ul>
            <div className="text-[10px] text-slate-400 mt-2 pt-1.5 border-t border-slate-800 italic">
              Computed from configurable risk weights (risk.yaml)
            </div>
          </div>
        )}
      </div>
    );
  };

  const getStatusBadge = (status: string) => {
    const config: Record<string, { bg: string; label: string }> = {
      validated: { bg: 'bg-blue-50 text-blue-700 border-blue-200', label: 'Awaiting review' },
      under_review: { bg: 'bg-amber-50 text-amber-800 border-amber-200', label: 'Under review' },
      evidence_requested: { bg: 'bg-purple-50 text-purple-800 border-purple-200', label: 'Evidence requested' },
      escalated: { bg: 'bg-red-50 text-red-800 border-red-200', label: 'Escalated' },
      closed: { bg: 'bg-emerald-50 text-emerald-800 border-emerald-200', label: 'Closed' },
      processing: { bg: 'bg-slate-50 text-slate-600 border-slate-200', label: 'Processing' },
    };

    const item = config[status] || { bg: 'bg-slate-100 text-slate-700 border-slate-200', label: status };

    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border ${item.bg}`}>
        {item.label}
      </span>
    );
  };

  return (
    <div className="space-y-4">
      {/* Top Banner / Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Scrutiny Triage Queue
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Auto-triaged by explainable risk points. Click an application to inspect findings & bounding boxes.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Search Box */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search institution or app no..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-600 focus:bg-white w-56 transition-all"
            />
          </div>

          {/* Band Filter */}
          <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200 text-xs">
            {['all', 'High', 'Medium', 'Low'].map((band) => (
              <button
                key={band}
                onClick={() => setBandFilter(band)}
                className={`px-2.5 py-1 rounded-md font-medium capitalize transition-all ${
                  bandFilter === band
                    ? 'bg-white text-slate-900 shadow-xs font-semibold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {band}
              </button>
            ))}
          </div>

          {/* Refresh Button */}
          <button
            onClick={fetchQueue}
            disabled={loading}
            className="p-1.5 text-slate-600 hover:text-blue-900 hover:bg-slate-100 rounded-lg border border-slate-200 transition-colors"
            title="Refresh queue"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {loading && applications.length === 0 ? (
          <div className="p-12 text-center text-slate-400 text-sm flex flex-col items-center justify-center gap-2">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
            <span>Loading applications from triage database...</span>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-red-600 text-sm">
            <AlertCircle className="w-6 h-6 mx-auto mb-2 text-red-500" />
            {error}
          </div>
        ) : filteredApps.length === 0 ? (
          <div className="p-12 text-center text-slate-500 text-sm">
            No applications match the current search / filter criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
                  <th className="py-3 px-4">Application & Institution</th>
                  <th className="py-3 px-3">Category</th>
                  <th className="py-3 px-3 text-center">Risk Triage</th>
                  <th className="py-3 px-3 text-center">Finding Discrepancies</th>
                  <th className="py-3 px-3 text-center">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredApps.map((app, index) => (
                  <tr
                    key={app.id}
                    onClick={() => onSelectApplication(app.id)}
                    className="hover:bg-blue-50/40 cursor-pointer transition-colors group"
                  >
                    {/* Institution & App details */}
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-900 text-sm group-hover:text-blue-900 transition-colors">
                        {app.institution_name || app.institution}
                      </div>
                      <div className="text-slate-500 text-[11px] flex items-center gap-2 mt-0.5">
                        <span className="font-mono text-slate-600">{app.application_no || app.no}</span>
                        <span>•</span>
                        <span>ID: <strong className="text-slate-700">{app.institution_id}</strong></span>
                        {app.submitted_on && (
                          <>
                            <span>•</span>
                            <span>Submitted: {formatDate(app.submitted_on)}</span>
                          </>
                        )}
                      </div>
                    </td>

                    {/* Category */}
                    <td className="py-3 px-3">
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium text-[11px] border border-slate-200">
                        {getCategoryLabel(app.category)}
                      </span>
                    </td>

                    {/* Risk Band & Score */}
                    <td className="py-3 px-3 text-center">
                      {getRiskBandBadge(app.risk_band, app.risk_score, app.risk_breakdown, index)}
                    </td>

                    {/* Finding Severity Counts */}
                    <td className="py-3 px-3 text-center">
                      <div className="inline-flex items-center gap-1.5">
                        {/* Critical */}
                        <span
                          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded font-mono text-[11px] font-bold ${
                            app.counts.critical > 0
                              ? 'bg-red-100 text-red-700 border border-red-200'
                              : 'bg-slate-100 text-slate-400'
                          }`}
                          title="Critical"
                        >
                          <AlertCircle className="w-3 h-3" />
                          {app.counts.critical}
                        </span>

                        {/* Warning */}
                        <span
                          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded font-mono text-[11px] font-bold ${
                            app.counts.warning > 0
                              ? 'bg-amber-100 text-amber-700 border border-amber-200'
                              : 'bg-slate-100 text-slate-400'
                          }`}
                          title="Warning"
                        >
                          <AlertTriangle className="w-3 h-3" />
                          {app.counts.warning}
                        </span>

                        {/* Info */}
                        <span
                          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded font-mono text-[11px] font-bold ${
                            app.counts.info > 0
                              ? 'bg-blue-100 text-blue-700 border border-blue-200'
                              : 'bg-slate-100 text-slate-400'
                          }`}
                          title="Info"
                        >
                          <Info className="w-3 h-3" />
                          {app.counts.info}
                        </span>
                      </div>
                    </td>

                    {/* Status */}
                    <td className="py-3 px-3 text-center">
                      {getStatusBadge(app.status)}
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-4 text-right">
                      <div className="inline-flex items-center gap-2">
                        {/* Download Inspection Brief */}
                        <a
                          href={api.getBriefPdfUrl(app.id)}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="p-1 text-slate-500 hover:text-blue-900 hover:bg-slate-100 rounded transition-colors"
                          title="Download Inspection Brief PDF"
                        >
                          <FileText className="w-4 h-4" />
                        </a>

                        {/* Re-run Pipeline */}
                        <button
                          onClick={(e) => handleReRun(e, app.id)}
                          disabled={reRunningId === app.id}
                          className="p-1 text-slate-500 hover:text-blue-900 hover:bg-slate-100 rounded transition-colors"
                          title="Re-run Scrutiny Checks"
                        >
                          <RefreshCw
                            className={`w-3.5 h-3.5 ${
                              reRunningId === app.id ? 'animate-spin text-blue-600' : ''
                            }`}
                          />
                        </button>

                        {/* Open Arrow */}
                        <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-blue-800 group-hover:translate-x-0.5 transition-all" />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
