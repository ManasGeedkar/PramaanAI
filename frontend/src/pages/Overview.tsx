import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { SystemStats } from '../api/types';
import {
  FileStack,
  AlertOctagon,
  CheckCircle,
  Timer,
  RefreshCw,
  ShieldCheck,
  Building,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

export const Overview: React.FC = () => {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getStats();
      setStats(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load system statistics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="p-16 flex flex-col items-center justify-center text-slate-400 gap-3">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-700" />
        <span className="text-sm font-medium">Loading management intelligence metrics...</span>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="p-8 bg-red-50 text-red-700 border border-red-200 rounded-xl text-center text-sm">
        {error || 'Unable to retrieve dashboard metrics.'}
      </div>
    );
  }

  // Prepare chart data for risk bands
  const bandChartData = [
    { name: 'High Risk', count: stats.by_band.High, color: '#dc2626' },
    { name: 'Medium Risk', count: stats.by_band.Medium, color: '#d97706' },
    { name: 'Low Risk', count: stats.by_band.Low, color: '#16a34a' },
  ];

  // Prepare chart data for verification statuses
  const statusLabels: Record<string, { label: string; color: string }> = {
    verified: { label: 'Verified', color: '#16a34a' },
    mismatch: { label: 'Mismatch', color: '#dc2626' },
    expired: { label: 'Expired', color: '#ea580c' },
    pending: { label: 'Pending', color: '#2563eb' },
    source_unavailable: { label: 'Unavailable', color: '#9333ea' },
    manual_review: { label: 'Manual Review', color: '#ca8a04' },
  };

  const verifChartData = Object.entries(stats.by_verification_status || {}).map(([st, count]) => ({
    name: statusLabels[st]?.label || st,
    count,
    color: statusLabels[st]?.color || '#64748b',
  }));

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Management Overview & Impact KPIs
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Operational throughput, automated document clearance, and scrutiny labor savings.
          </p>
        </div>
        <button
          onClick={fetchStats}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 shadow-2xs transition-all"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh Data</span>
        </button>
      </div>

      {/* KPI Cards (4 key metrics) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1: Applications */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Total Applications
            </span>
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center">
              <FileStack className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900 font-mono">
              {stats.total_applications}
            </span>
            <span className="text-xs text-slate-500">active submissions</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-500 border-t border-slate-100 pt-2 flex items-center gap-1">
            <Building className="w-3 h-3 text-slate-400" />
            <span>Across 10 synthetic technical institutions</span>
          </div>
        </div>

        {/* KPI 2: High Risk Queue */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              High-Risk Queue
            </span>
            <div className="w-8 h-8 rounded-lg bg-red-50 text-red-600 flex items-center justify-center">
              <AlertOctagon className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-red-600 font-mono">
              {stats.high_risk_count}
            </span>
            <span className="text-xs text-red-600 font-medium">
              ({Math.round((stats.high_risk_count / stats.total_applications) * 100)}% of queue)
            </span>
          </div>
          <div className="mt-2 text-[11px] text-slate-500 border-t border-slate-100 pt-2 flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500"></span>
            <span>Priority scrutiny required before approval</span>
          </div>
        </div>

        {/* KPI 3: Documents Auto-Cleared */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Documents Auto-Cleared
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <CheckCircle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-emerald-700 font-mono">
              {stats.documents_auto_cleared}
            </span>
            <span className="text-xs text-slate-500">
              / {stats.total_documents} total ({Math.round((stats.documents_auto_cleared / stats.total_documents) * 100)}%)
            </span>
          </div>
          <div className="mt-2 text-[11px] text-slate-500 border-t border-slate-100 pt-2 flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 text-emerald-500" />
            <span>No critical or warning findings</span>
          </div>
        </div>

        {/* KPI 4: Estimated Hours Saved */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Estimated Hours Saved
            </span>
            <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-700 flex items-center justify-center">
              <Timer className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-purple-700 font-mono">
              {stats.hours_saved}
            </span>
            <span className="text-xs text-purple-700 font-semibold">officer hours saved</span>
          </div>
          <div className="mt-2 text-[10px] text-slate-400 border-t border-slate-100 pt-2 leading-tight">
            {stats.hours_saved_assumption}
          </div>
        </div>
      </div>

      {/* Two Column Visualisation Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Chart 1: Applications by Risk Band */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Application Distribution by Risk Band
              </h3>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Explainable classification based on critical, warning, and consistency points.
              </p>
            </div>
            <div className="flex items-center gap-2 text-[11px]">
              <span className="flex items-center gap-1 text-slate-600">
                <span className="w-2 h-2 rounded-full bg-red-500"></span> High (&gt;=60)
              </span>
              <span className="flex items-center gap-1 text-slate-600">
                <span className="w-2 h-2 rounded-full bg-amber-500"></span> Medium (20-59)
              </span>
              <span className="flex items-center gap-1 text-slate-600">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Low (&lt;20)
              </span>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={bandChartData} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#475569' }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#475569' }} />
                <Tooltip
                  formatter={(value: any) => [`${value} applications`, 'Count']}
                  contentStyle={{ backgroundColor: '#0f172a', borderRadius: '8px', color: '#fff', fontSize: '12px' }}
                />
                <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={60}>
                  {bandChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Document Verification Statuses */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Source Registry Verification Statuses
              </h3>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Breakdown of mock registry calls across Fire NOC, Land, University & AICTE.
              </p>
            </div>
            <span className="text-[11px] font-mono font-bold text-slate-500">
              6 Status Types
            </span>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={verifChartData} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 10, fill: '#475569' }}
                  interval={0}
                  angle={-15}
                  textAnchor="end"
                  height={35}
                />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#475569' }} />
                <Tooltip
                  formatter={(value: any) => [`${value} verifications`, 'Count']}
                  contentStyle={{ backgroundColor: '#0f172a', borderRadius: '8px', color: '#fff', fontSize: '12px' }}
                />
                <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={45}>
                  {verifChartData.map((entry, index) => (
                    <Cell key={`cell-verif-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
