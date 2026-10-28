import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type {
  ApplicationDetail as ApplicationDetailType,
  DocumentItem,
  VerificationStatus,
  FindingSeverity,
} from '../api/types';
import { DocumentViewer, type BoundingBox } from '../components/DocumentViewer';
import {
  ArrowLeft,
  FileText,
  RefreshCw,
  AlertTriangle,
  AlertOctagon,
  Info,
  CheckCircle2,
  XCircle,
  ShieldAlert,
  Columns,
  X,
  Layers,
  Flame,
  Network,
  Edit3,
  Save,
} from 'lucide-react';
import { EntityGraph } from '../components/EntityGraph';
import { formatDate, formatDateTime } from '../utils/date';

interface ApplicationDetailProps {
  applicationId?: number | string;
  onBack?: () => void;
}

// Friendly document type labels
const DOC_TYPE_LABELS: Record<string, string> = {
  fire_noc: 'Fire Safety NOC',
  land_deed: 'Land / Sale Deed',
  affiliation_letter: 'University Affiliation Letter',
  accreditation_certificate: 'Programme Accreditation Certificate',
  faculty_list: 'Faculty List',
  affidavit: 'Affidavit cum Undertaking',
  'photo:computer_lab': 'Photo: Computer Lab',
  'photo:classroom': 'Photo: Classroom',
};

// Required docs per category from checklists.yaml
const CHECKLIST_REQUIREMENTS: Record<
  string,
  { required: string[]; optional: string[]; photos: string[] }
> = {
  EoA: {
    required: ['fire_noc', 'land_deed', 'affiliation_letter', 'faculty_list', 'affidavit'],
    optional: ['accreditation_certificate'],
    photos: ['photo:computer_lab', 'photo:classroom'],
  },
  EoA_INTAKE_INCREASE: {
    required: [
      'fire_noc',
      'land_deed',
      'affiliation_letter',
      'faculty_list',
      'affidavit',
      'accreditation_certificate',
    ],
    optional: [],
    photos: ['photo:computer_lab', 'photo:classroom'],
  },
};

export const ApplicationDetail: React.FC<ApplicationDetailProps> = ({
  applicationId,
  onBack,
}) => {
  const params = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const currentAppId = applicationId ?? params.id;

  const [app, setApp] = useState<ApplicationDetailType | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [reRunning, setReRunning] = useState<boolean>(false);

  // Selected finding
  const [selectedFindingId, setSelectedFindingId] = useState<number | null>(null);

  // Active document in single viewer
  const [activeDocId, setActiveDocId] = useState<number | null>(null);
  const [activePage, setActivePage] = useState<number>(1);

  // Side-by-side view mode
  const [isSideBySide, setIsSideBySide] = useState<boolean>(false);
  const [sideBySideDocs, setSideBySideDocs] = useState<{
    left: { doc: DocumentItem; boxes: BoundingBox[]; page: number } | null;
    right: { doc: DocumentItem; boxes: BoundingBox[]; page: number } | null;
  }>({ left: null, right: null });

  // Finding filter
  const [severityFilter, setSeverityFilter] = useState<'all' | FindingSeverity>('all');

  // Review comment state keyed by finding ID
  const [reviewComments, setReviewComments] = useState<Record<number, string>>({});
  const [openCommentForId, setOpenCommentForId] = useState<number | null>(null);
  const [reviewingId, setReviewingId] = useState<number | null>(null);
  const [reviewSuccessMsg, setReviewSuccessMsg] = useState<string | null>(null);

  // Page tab: scrutiny vs entity graph (survives refresh via ?tab=graph)
  const [pageTab, setPageTab] = useState<'scrutiny' | 'entity_graph'>(() => {
    return searchParams.get('tab') === 'graph' ? 'entity_graph' : 'scrutiny';
  });

  // Sync pageTab if searchParams change
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    if (tabParam === 'graph' && pageTab !== 'entity_graph') {
      setPageTab('entity_graph');
    } else if (!tabParam && pageTab !== 'scrutiny') {
      setPageTab('scrutiny');
    }
  }, [searchParams]);

  // Bottom section active tab
  const [bottomTab, setBottomTab] = useState<'verifications' | 'checklist' | 'fields'>('verifications');

  // Human correction state for unreadable fields
  const [editingFieldId, setEditingFieldId] = useState<number | null>(null);
  const [editValues, setEditValues] = useState<Record<number, string>>({});
  const [editComments, setEditComments] = useState<Record<number, string>>({});
  const [savingFieldId, setSavingFieldId] = useState<number | null>(null);

  const handleSaveCorrection = async (fieldId: number) => {
    const val = editValues[fieldId];
    if (val === undefined || val === null || val.trim() === '') return;
    const comment = editComments[fieldId] || 'Manual human verification by scrutiny officer';
    try {
      setSavingFieldId(fieldId);
      await api.correctField(fieldId, val.trim(), comment);
      setReviewSuccessMsg(`Field successfully corrected to "${val.trim()}". Audit log entry created.`);
      setEditingFieldId(null);
      // Re-fetch details to show updated value
      await fetchDetail();
    } catch (err: any) {
      alert(`Failed to save correction: ${err.message}`);
    } finally {
      setSavingFieldId(null);
    }
  };

  const fetchDetail = async () => {
    if (!currentAppId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await api.getApplication(currentAppId);
      setApp(data);

      // Default active document
      if (data.documents && data.documents.length > 0 && !activeDocId) {
        setActiveDocId(data.documents[0].id);
      }

      // Check if finding is specified in URL search params (prioritize numeric ID, fallback to code)
      const findingQuery = searchParams.get('finding');
      let targetFinding = null;
      if (findingQuery && data.findings && data.findings.length > 0) {
        targetFinding =
          data.findings.find((f) => String(f.id) === findingQuery) ||
          data.findings.find((f) => f.code === findingQuery);
      }

      if (targetFinding) {
        setSelectedFindingId(targetFinding.id);
      } else if (data.findings && data.findings.length > 0) {
        const firstCrit = data.findings.find((f) => f.severity === 'critical') || data.findings[0];
        setSelectedFindingId(firstCrit.id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load application details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [currentAppId]);

  // When selected finding changes, update active document(s) & highlight boxes
  useEffect(() => {
    if (!app || !selectedFindingId) return;

    const finding = (app.findings || []).find((f) => f.id === selectedFindingId);
    if (!finding) return;

    const evidenceItems = finding.evidence?.items || [];

    // Check if finding is CROSS_DOC_MISMATCH with 2 distinct documents
    const docItems = evidenceItems.filter((it) => it.document_id !== null && it.document_id !== undefined);
    const uniqueDocIds = Array.from(new Set(docItems.map((it) => it.document_id!)));

    if (finding.code === 'CROSS_DOC_MISMATCH' && uniqueDocIds.length >= 2) {
      // Setup side-by-side view
      const doc1 = (app.documents || []).find((d) => d.id === uniqueDocIds[0]);
      const doc2 = (app.documents || []).find((d) => d.id === uniqueDocIds[1]);

      const item1 = docItems.find((it) => it.document_id === uniqueDocIds[0]);
      const item2 = docItems.find((it) => it.document_id === uniqueDocIds[1]);

      if (doc1 && doc2) {
        setSideBySideDocs({
          left: {
            doc: doc1,
            page: item1?.page || 1,
            boxes: item1?.bbox
              ? [{ bbox: item1.bbox, field: item1.field, value: item1.value }]
              : [],
          },
          right: {
            doc: doc2,
            page: item2?.page || 1,
            boxes: item2?.bbox
              ? [{ bbox: item2.bbox, field: item2.field, value: item2.value }]
              : [],
          },
        });
        setIsSideBySide(true);
        return;
      }
    }

    // Single document view
    setIsSideBySide(false);
    if (docItems.length > 0 && docItems[0].document_id) {
      setActiveDocId(docItems[0].document_id);
      setActivePage(docItems[0].page || 1);
    } else if (finding.document_id) {
      setActiveDocId(finding.document_id);
      setActivePage(1);
    }
  }, [selectedFindingId, app]);

  const handleReRun = async () => {
    if (!currentAppId) return;
    try {
      setReRunning(true);
      await api.runApplicationPipeline(currentAppId);
      await fetchDetail();
      setReviewSuccessMsg('Scrutiny pipeline re-run completed successfully.');
      setTimeout(() => setReviewSuccessMsg(null), 4000);
    } catch (err: any) {
      alert(`Re-run failed: ${err.message}`);
    } finally {
      setReRunning(false);
    }
  };

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      navigate('/queue');
    }
  };

  const handleTabSwitch = (newTab: 'scrutiny' | 'entity_graph') => {
    setPageTab(newTab);
    const nextParams = new URLSearchParams(searchParams);
    if (newTab === 'entity_graph') {
      nextParams.set('tab', 'graph');
    } else {
      nextParams.delete('tab');
    }
    setSearchParams(nextParams, { replace: true });
  };

  // Sync state if URL search parameters change (Back/Forward navigation)
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    setPageTab(tabParam === 'graph' ? 'entity_graph' : 'scrutiny');

    const findingQuery = searchParams.get('finding');
    if (findingQuery && app?.findings && app.findings.length > 0) {
      const match =
        app.findings.find((f) => String(f.id) === findingQuery) ||
        app.findings.find((f) => f.code === findingQuery);
      if (match && match.id !== selectedFindingId) {
        setSelectedFindingId(match.id);
      }
    }
  }, [searchParams, app?.findings]);

  const handleFindingSelect = (finding: any) => {
    setSelectedFindingId(finding.id);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set('finding', String(finding.id));
    setSearchParams(nextParams, { replace: true });
  };

  const handleReviewAction = async (
    findingId: number,
    decision: 'accept' | 'dismiss' | 'request_evidence' | 'escalate'
  ) => {
    try {
      setReviewingId(findingId);
      const comment = reviewComments[findingId] || '';
      const res = await api.reviewFinding(findingId, decision, comment);

      // Update state in place
      if (app) {
        const updatedFindings = app.findings.map((f) =>
          f.id === findingId ? { ...f, status: res.finding.status } : f
        );
        setApp({
          ...app,
          status: res.application.status,
          risk_score: res.application.risk_score,
          risk_band: res.application.risk_band,
          risk_breakdown: res.application.risk_breakdown,
          findings: updatedFindings,
        });
      }

      setOpenCommentForId(null);
      setReviewSuccessMsg(
        `Finding updated to "${res.finding.status}". Application status is now "${res.application.status}".`
      );
      setTimeout(() => setReviewSuccessMsg(null), 4000);
    } catch (err: any) {
      alert(`Review action failed: ${err.message}`);
    } finally {
      setReviewingId(null);
    }
  };

  // Helper labels & styling
  const getCategoryLabel = (category: string) => {
    if (category === 'EoA') return 'EoA';
    if (category === 'EoA_INTAKE_INCREASE') return 'EoA + Intake increase';
    return category ? category.replace(/_/g, ' ') : '';
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
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${item.bg}`}>
        {item.label}
      </span>
    );
  };

  const getVerificationStatusChip = (status: VerificationStatus) => {
    const config: Record<VerificationStatus, { bg: string; text: string; label: string }> = {
      verified: { bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700', label: 'Verified' },
      mismatch: { bg: 'bg-red-50 border-red-200', text: 'text-red-700', label: 'Mismatch' },
      expired: { bg: 'bg-amber-50 border-amber-200', text: 'text-amber-800', label: 'Expired' },
      pending: { bg: 'bg-sky-50 border-sky-200', text: 'text-sky-700', label: 'Pending' },
      source_unavailable: { bg: 'bg-slate-100 border-slate-300', text: 'text-slate-700', label: 'Source Unavailable' },
      manual_review: { bg: 'bg-purple-50 border-purple-200', text: 'text-purple-700', label: 'Manual Review' },
    };
    const c = config[status] || { bg: 'bg-slate-100 border-slate-200', text: 'text-slate-700', label: status };
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider border ${c.bg} ${c.text}`}>
        {c.label}
      </span>
    );
  };

  const renderEvidenceLine = (finding: any) => {
    const items = finding.evidence?.items || [];
    const expected = finding.evidence?.expected;

    if (items.length === 0 && !expected) return null;

    if (items.length === 0) {
      return (
        <div className="mt-1.5 text-[10.5px] text-slate-600 font-mono">
          <span className="font-semibold text-slate-700">Evidence:</span> Expected: {expected}
        </div>
      );
    }

    if (items.length === 1) {
      const it = items[0];
      const docName = DOC_TYPE_LABELS[it.doc_type || ''] || it.doc_type || 'Document';
      return (
        <div className="mt-1.5 text-[10.5px] text-slate-600 font-mono flex flex-wrap items-center gap-1.5">
          <span className="font-semibold text-slate-700">Evidence:</span>
          <span>{docName}</span>
          {it.field && <span>• Field: <strong className="text-slate-800">{it.field}</strong></span>}
          {it.value && <span>• Found: <strong className="text-red-700">{it.value}</strong></span>}
          {expected && <span>• Expected: <strong className="text-emerald-700">{expected}</strong></span>}
        </div>
      );
    }

    // Multiple items (e.g. CROSS_DOC_MISMATCH)
    return (
      <div className="mt-1.5 text-[10.5px] text-slate-600 font-mono flex flex-wrap items-center gap-1.5">
        <span className="font-semibold text-slate-700">Evidence:</span>
        {items
          .filter((it: any) => it.doc_type || it.value)
          .map((it: any, idx: number) => (
            <span key={idx}>
              {idx > 0 && <span className="text-slate-400"> vs </span>}
              {DOC_TYPE_LABELS[it.doc_type || ''] || it.doc_type} (<strong className="text-red-700">{it.value || 'N/A'}</strong>)
            </span>
          ))}
        {items[0]?.field && <span>• Field: <strong className="text-slate-800">{items[0].field}</strong></span>}
        {expected && <span>• Expected: <strong className="text-emerald-700">{expected}</strong></span>}
      </div>
    );
  };

  // Active document & bounding boxes for single view
  const activeDocument = useMemo(() => {
    if (!app || !activeDocId) return null;
    return (app.documents || []).find((d) => d.id === activeDocId) || (app.documents || [])[0] || null;
  }, [app, activeDocId]);

  const activeFinding = useMemo(() => {
    if (!app || !selectedFindingId) return null;
    return (app.findings || []).find((f) => f.id === selectedFindingId) || null;
  }, [app, selectedFindingId]);

  const activeHighlightBoxes = useMemo((): BoundingBox[] => {
    if (!activeFinding || !activeDocument) return [];
    const items = activeFinding.evidence?.items || [];
    return items
      .filter((it) => it.document_id === activeDocument.id && it.bbox)
      .map((it) => ({
        bbox: it.bbox!,
        field: it.field,
        value: it.value,
      }));
  }, [activeFinding, activeDocument]);

  const filteredFindings = useMemo(() => {
    if (!app) return [];
    if (severityFilter === 'all') return app.findings || [];
    return (app.findings || []).filter((f) => f.severity === severityFilter);
  }, [app, severityFilter]);

  // Check which tabs have findings (strictly counting number of findings per document)
  const documentFindingCounts = useMemo(() => {
    const counts: Record<number, number> = {};
    if (!app) return counts;
    for (const f of app.findings || []) {
      const docIds = new Set<number>();
      if (f.document_id) {
        docIds.add(f.document_id);
      }
      if (f.evidence?.items) {
        for (const it of f.evidence.items) {
          if (it.document_id) {
            docIds.add(it.document_id);
          }
        }
      }
      for (const dId of docIds) {
        counts[dId] = (counts[dId] || 0) + 1;
      }
    }
    return counts;
  }, [app]);

  if (loading) {
    return (
      <div className="p-20 flex flex-col items-center justify-center text-slate-400 gap-3">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-700" />
        <span className="text-sm font-medium">Loading application dossier & documents...</span>
      </div>
    );
  }

  if (error || !app) {
    return (
      <div className="p-8 bg-red-50 text-red-700 border border-red-200 rounded-xl text-center text-sm">
        <p className="font-semibold mb-2">Error loading application #{currentAppId}</p>
        <p>{error}</p>
        <button
          onClick={handleBack}
          className="mt-4 px-4 py-1.5 bg-white border border-red-300 text-red-800 rounded-lg text-xs font-semibold hover:bg-red-100"
        >
          Return to Triage Queue
        </button>
      </div>
    );
  }

  const bandColors = {
    High: 'bg-red-50 text-red-700 border-red-200',
    Medium: 'bg-amber-50 text-amber-700 border-amber-200',
    Low: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  }[app.risk_band || 'Low'];

  const checklistConfig =
    CHECKLIST_REQUIREMENTS[app.category] || CHECKLIST_REQUIREMENTS.EoA;

  return (
    <div className="space-y-4">
      {/* Toast Alert */}
      {reviewSuccessMsg && (
        <div className="bg-emerald-50 border border-emerald-300 text-emerald-800 px-4 py-2.5 rounded-lg text-xs font-medium flex items-center justify-between shadow-xs animate-in fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>{reviewSuccessMsg}</span>
          </div>
          <button
            onClick={() => setReviewSuccessMsg(null)}
            className="text-emerald-700 hover:text-emerald-900"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Header Bar */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <button
              onClick={handleBack}
              className="p-2 text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded-lg border border-slate-200 transition-colors mt-0.5"
              title="Back to queue"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <div>
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                  {app.institution_name}
                </h1>

                {/* Risk Band Badge with breakdown popover */}
                <div className="relative group inline-block">
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-bold border cursor-help ${bandColors}`}
                  >
                    {app.risk_band} ({app.risk_score} pts)
                  </span>

                  {app.risk_breakdown && app.risk_breakdown.length > 0 && (
                    <div className="absolute left-0 top-full mt-1.5 hidden group-hover:block z-50 w-72 p-3 bg-slate-900 text-white text-xs rounded-lg shadow-xl border border-slate-700 pointer-events-none">
                      <div className="font-semibold text-slate-200 pb-1.5 mb-1.5 border-b border-slate-700 flex justify-between">
                        <span>Risk Breakdown</span>
                        <span className="font-mono text-emerald-400">{app.risk_score} pts</span>
                      </div>
                      <ul className="space-y-1 text-[11px] max-h-44 overflow-y-auto">
                        {app.risk_breakdown.map((item, i) => (
                          <li key={i} className="flex justify-between items-start gap-2">
                            <span className="text-slate-300 leading-tight">{item.reason}</span>
                            <span className="font-mono font-bold text-amber-400 flex-shrink-0">
                              +{item.points}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {getStatusBadge(app.status)}
              </div>

              {/* Dossier Subtitle */}
              <div className="text-xs text-slate-500 flex flex-wrap items-center gap-2 mt-1.5 font-mono">
                <span>{app.application_no}</span>
                <span>•</span>
                <span>AICTE ID: {app.aicte_id}</span>
                <span>•</span>
                <span>Category: {getCategoryLabel(app.category)}</span>
                <span>•</span>
                <span>Academic Session: {app.academic_year}</span>
                {app.submitted_on && (
                  <>
                    <span>•</span>
                    <span>Submitted: {formatDate(app.submitted_on)}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={handleReRun}
              disabled={reRunning}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 shadow-2xs transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${reRunning ? 'animate-spin text-blue-600' : ''}`} />
              <span>{reRunning ? 'Running Checks...' : 'Re-run Checks'}</span>
            </button>

            <a
              href={api.getBriefPdfUrl(app.id)}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-blue-900 hover:bg-blue-800 rounded-lg shadow-xs transition-colors"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Download Inspection Brief</span>
            </a>
          </div>
        </div>
      </div>

      {/* Primary Navigation Tabs */}
      <div className="flex items-center gap-2 bg-white p-1.5 rounded-lg border border-slate-200 w-fit">
        <button
          onClick={() => handleTabSwitch('scrutiny')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-bold transition-all ${
            pageTab === 'scrutiny'
              ? 'bg-blue-900 text-white shadow-xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Document Scrutiny</span>
        </button>
        <button
          onClick={() => handleTabSwitch('entity_graph')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-bold transition-all ${
            pageTab === 'entity_graph'
              ? 'bg-blue-900 text-white shadow-xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <Network className="w-4 h-4" />
          <span>Entity Relationship Graph</span>
        </button>
      </div>

      {pageTab === 'entity_graph' ? (
        <EntityGraph applicationId={app.id} />
      ) : (
        <>
          {/* Main Two-Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            {/* Left Column: Findings List (5 columns) */}
            <div className="lg:col-span-5 space-y-3">
              <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
            {/* Findings Header & Filter */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-blue-900" />
                <h2 className="text-sm font-bold text-slate-900">
                  Scrutiny Findings ({(app.findings || []).length})
                </h2>
              </div>

              {/* Severity Filter Pills */}
              <div className="flex items-center gap-1 text-[11px]">
                {(['all', 'critical', 'warning', 'info'] as const).map((sev) => {
                  const count =
                    sev === 'all'
                      ? (app.findings || []).length
                      : (app.findings || []).filter((f) => f.severity === sev).length;
                  return (
                    <button
                      key={sev}
                      onClick={() => setSeverityFilter(sev)}
                      className={`px-2 py-0.5 rounded font-semibold capitalize transition-all ${
                        severityFilter === sev
                          ? 'bg-blue-900 text-white'
                          : 'text-slate-600 hover:bg-slate-100'
                      }`}
                    >
                      {sev} ({count})
                    </button>
                  );
                })}
              </div>
            </div>

            <p className="text-[11px] text-slate-500 italic mt-2">
              Advisory findings for scrutiny verification — not a final determination. Click a finding to view evidence highlights.
            </p>

            {/* Findings Card List */}
            <div className="mt-3 space-y-2.5 max-h-[750px] overflow-y-auto pr-1">
              {filteredFindings.length === 0 ? (
                <div className="p-8 text-center text-xs text-slate-400">
                  No findings match this filter.
                </div>
              ) : (
                filteredFindings.map((finding) => {
                  const isSelected = selectedFindingId === finding.id;
                  const isTamper = finding.code === 'TAMPER_SUSPECTED';
                  const isCrossDoc = finding.code === 'CROSS_DOC_MISMATCH';

                  const sevConfig = {
                    critical: {
                      badge: 'bg-red-50 text-red-700 border-red-200',
                      border: isSelected ? 'border-red-500 ring-2 ring-red-200' : 'border-red-200 hover:border-red-300',
                      icon: AlertOctagon,
                    },
                    warning: {
                      badge: 'bg-amber-50 text-amber-800 border-amber-200',
                      border: isSelected ? 'border-amber-500 ring-2 ring-amber-200' : 'border-amber-200 hover:border-amber-300',
                      icon: AlertTriangle,
                    },
                    info: {
                      badge: 'bg-blue-50 text-blue-700 border-blue-200',
                      border: isSelected ? 'border-blue-500 ring-2 ring-blue-200' : 'border-slate-200 hover:border-slate-300',
                      icon: Info,
                    },
                  }[finding.severity];

                  const SevIcon = sevConfig.icon;

                  const statusLabels: Record<string, string> = {
                    open: 'Open',
                    accepted: 'Accepted',
                    dismissed: 'Dismissed',
                    evidence_requested: 'Evidence Requested',
                    escalated: 'Escalated',
                  };

                  return (
                    <div
                      key={finding.id}
                      onClick={() => handleFindingSelect(finding)}
                      className={`p-3.5 rounded-lg border transition-all cursor-pointer bg-white text-left ${sevConfig.border} ${
                        isSelected ? 'bg-slate-50/70 shadow-xs' : 'hover:bg-slate-50/40'
                      }`}
                    >
                      {/* Top Header of Card */}
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wider ${sevConfig.badge}`}
                          >
                            <SevIcon className="w-3 h-3" />
                            {finding.severity}
                          </span>

                          <span className="font-mono text-[11px] font-bold text-slate-800 bg-slate-100 px-1.5 py-0.5 rounded">
                            {finding.code}
                          </span>

                          {finding.confidence !== null && finding.confidence !== undefined && (
                            <span className="text-[10px] text-slate-700 font-mono bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
                              {finding.code === 'TAMPER_SUSPECTED'
                                ? `ELA ratio ${finding.confidence}× (threshold 1.6×)`
                                : `Conf: ${
                                    finding.confidence <= 1.0
                                      ? Math.round(finding.confidence * 100)
                                      : Math.min(100, Math.round(finding.confidence))
                                  }%`}
                            </span>
                          )}
                        </div>

                        {/* Finding Status Chip */}
                        <span
                          className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${
                            finding.status === 'dismissed'
                              ? 'bg-slate-100 text-slate-500 line-through border-slate-200'
                              : finding.status === 'escalated'
                              ? 'bg-red-100 text-red-800 border-red-300 font-bold'
                              : finding.status === 'accepted'
                              ? 'bg-blue-100 text-blue-800 border-blue-300 font-bold'
                              : finding.status === 'evidence_requested'
                              ? 'bg-purple-100 text-purple-800 border-purple-300 font-bold'
                              : 'bg-slate-100 text-slate-700 border-slate-200'
                          }`}
                        >
                          {statusLabels[finding.status] || finding.status}
                        </span>
                      </div>

                      {/* Title & Message */}
                      <h4 className="text-xs font-bold text-slate-900 leading-snug">
                        {finding.title}
                      </h4>
                      <p className="text-[11px] text-slate-600 mt-1 leading-relaxed">
                        {finding.message}
                      </p>

                      {/* Evidence Line */}
                      {renderEvidenceLine(finding)}

                      {/* What Changed: stacked document crop + ELA crop for TAMPER_SUSPECTED */}
                      {isTamper && (
                        <div className="mt-2.5 pt-2 border-t border-slate-200">
                          <div className="text-[10px] font-bold text-slate-800 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                            <Flame className="w-3.5 h-3.5 text-amber-600" />
                            <span>What changed</span>
                          </div>
                          <div className="overflow-hidden rounded-md border border-slate-300 shadow-2xs bg-slate-900">
                            <img
                              src={`/api/findings/${finding.id}/ela-crop.png`}
                              alt="What changed - Document Line vs ELA Heatmap"
                              className="w-full block object-contain"
                            />
                          </div>
                          <div className="flex justify-between items-center text-[9px] text-slate-500 mt-1 px-0.5 font-mono">
                            <span>Top: Original document line</span>
                            <span>Bottom: ELA heatmap (Hot colormap)</span>
                          </div>
                        </div>
                      )}

                      {/* Visual indicator badges */}
                      <div className="mt-2 flex items-center gap-2 text-[10px] text-slate-500">
                        {isTamper && (
                          <span className="inline-flex items-center gap-1 text-amber-700 font-semibold bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                            <Flame className="w-3 h-3" /> ELA Heatmap available
                          </span>
                        )}
                        {isCrossDoc && (
                          <span className="inline-flex items-center gap-1 text-purple-700 font-semibold bg-purple-50 px-1.5 py-0.5 rounded border border-purple-200">
                            <Columns className="w-3 h-3" /> Side-by-side comparison
                          </span>
                        )}
                      </div>

                      {/* Review Buttons & Comment Box */}
                      <div
                        className="mt-3 pt-2.5 border-t border-slate-200/80 flex flex-col gap-2"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div className="flex items-center justify-between gap-1 flex-wrap">
                          <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                            Review Action:
                          </span>

                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => handleReviewAction(finding.id, 'accept')}
                              disabled={reviewingId === finding.id}
                              className="px-2 py-1 text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 rounded hover:bg-emerald-100 transition-colors"
                              title="Accept finding as valid issue"
                            >
                              Accept
                            </button>

                            <button
                              onClick={() => handleReviewAction(finding.id, 'dismiss')}
                              disabled={reviewingId === finding.id}
                              className="px-2 py-1 text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200 rounded hover:bg-slate-200 transition-colors"
                              title="Dismiss finding (false positive / acceptable)"
                            >
                              Dismiss
                            </button>

                            <button
                              onClick={() => handleReviewAction(finding.id, 'request_evidence')}
                              disabled={reviewingId === finding.id}
                              className="px-2 py-1 text-[10px] font-semibold bg-purple-50 text-purple-700 border border-purple-200 rounded hover:bg-purple-100 transition-colors"
                              title="Request clarification or additional proof from institution"
                            >
                              Request Evidence
                            </button>

                            <button
                              onClick={() => handleReviewAction(finding.id, 'escalate')}
                              disabled={reviewingId === finding.id}
                              className="px-2 py-1 text-[10px] font-semibold bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100 transition-colors"
                              title="Escalate to hearing committee"
                            >
                              Escalate
                            </button>

                            <button
                              onClick={() =>
                                setOpenCommentForId(
                                  openCommentForId === finding.id ? null : finding.id
                                )
                              }
                              className={`p-1 text-[10px] rounded border transition-colors ${
                                openCommentForId === finding.id || reviewComments[finding.id]
                                  ? 'bg-blue-50 text-blue-700 border-blue-300'
                                  : 'text-slate-400 border-slate-200 hover:text-slate-600'
                              }`}
                              title="Add officer review notes"
                            >
                              <FileText className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>

                        {/* Collapsible Comment Box */}
                        {openCommentForId === finding.id && (
                          <div className="mt-1 flex items-center gap-1.5">
                            <input
                              type="text"
                              placeholder="Add review remark / rationale..."
                              value={reviewComments[finding.id] || ''}
                              onChange={(e) =>
                                setReviewComments({
                                  ...reviewComments,
                                  [finding.id]: e.target.value,
                                  })
                              }
                              className="flex-1 text-[11px] px-2 py-1 border border-slate-300 rounded bg-white focus:outline-none focus:ring-1 focus:ring-blue-600"
                            />
                            <span className="text-[10px] text-slate-400">Attached on action</span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Document Viewer (7 columns) */}
        <div className="lg:col-span-7 space-y-3">
          {/* Document Tabs */}
          <div className="bg-white p-2 rounded-xl border border-slate-200 shadow-2xs">
            <div className="flex items-center justify-between gap-2 overflow-x-auto pb-1 scrollbar-thin">
              <div className="flex items-center gap-1">
                {app.documents.map((doc) => {
                  const isActive = !isSideBySide && activeDocId === doc.id;
                  const label = DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type;
                  const findingCount = documentFindingCounts[doc.id] || 0;

                  return (
                    <button
                      key={doc.id}
                      onClick={() => {
                        setIsSideBySide(false);
                        setActiveDocId(doc.id);
                        setActivePage(1);
                      }}
                      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all whitespace-nowrap ${
                        isActive
                          ? 'bg-blue-900 text-white shadow-xs'
                          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                      }`}
                    >
                      <span>{label}</span>
                      {findingCount > 0 && (
                        <span
                          className={`w-4 h-4 rounded-full text-[10px] flex items-center justify-center font-bold ${
                            isActive
                              ? 'bg-red-500 text-white'
                              : 'bg-red-100 text-red-700'
                          }`}
                        >
                          {findingCount}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Side-by-side indicator / toggle */}
              {sideBySideDocs.left && sideBySideDocs.right && (
                <button
                  onClick={() => setIsSideBySide(!isSideBySide)}
                  className={`flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg border transition-all whitespace-nowrap ${
                    isSideBySide
                      ? 'bg-purple-900 text-white border-purple-900 shadow-xs'
                      : 'bg-white text-purple-700 border-purple-200 hover:bg-purple-50'
                  }`}
                  title="Toggle side-by-side document comparison"
                >
                  <Columns className="w-3.5 h-3.5" />
                  <span>{isSideBySide ? 'Side-by-Side (Active)' : 'Compare Documents'}</span>
                </button>
              )}
            </div>
          </div>

          {/* Active Viewer Container */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-2xs p-3">
            {isSideBySide && sideBySideDocs.left && sideBySideDocs.right ? (
              // Side-by-Side Viewer Mode (for CROSS_DOC_MISMATCH)
              <div className="space-y-2">
                {/* Side-by-side header banner */}
                <div className="bg-purple-50 border border-purple-200 px-3 py-2 rounded-lg text-xs text-purple-900 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Columns className="w-4 h-4 text-purple-600 flex-shrink-0" />
                    <span>
                      <strong>Cross-Document Comparison:</strong> Comparing{' '}
                      {DOC_TYPE_LABELS[sideBySideDocs.left.doc.doc_type] || sideBySideDocs.left.doc.doc_type} vs{' '}
                      {DOC_TYPE_LABELS[sideBySideDocs.right.doc.doc_type] || sideBySideDocs.right.doc.doc_type}
                    </span>
                  </div>
                  <button
                    onClick={() => setIsSideBySide(false)}
                    className="text-purple-700 hover:text-purple-900 font-semibold underline text-[11px]"
                  >
                    Switch to single view
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 min-h-[520px]">
                  {/* Left Document */}
                  <div className="flex flex-col h-[560px]">
                    <DocumentViewer
                      documentId={sideBySideDocs.left.doc.id}
                      docType={sideBySideDocs.left.doc.doc_type}
                      filePath={sideBySideDocs.left.doc.file_path}
                      initialPage={sideBySideDocs.left.page}
                      highlightBoxes={sideBySideDocs.left.boxes}
                      title={`${DOC_TYPE_LABELS[sideBySideDocs.left.doc.doc_type] || sideBySideDocs.left.doc.doc_type}`}
                      zoomTrigger={selectedFindingId}
                    />
                  </div>

                  {/* Right Document */}
                  <div className="flex flex-col h-[560px]">
                    <DocumentViewer
                      documentId={sideBySideDocs.right.doc.id}
                      docType={sideBySideDocs.right.doc.doc_type}
                      filePath={sideBySideDocs.right.doc.file_path}
                      initialPage={sideBySideDocs.right.page}
                      highlightBoxes={sideBySideDocs.right.boxes}
                      title={`${DOC_TYPE_LABELS[sideBySideDocs.right.doc.doc_type] || sideBySideDocs.right.doc.doc_type}`}
                      zoomTrigger={selectedFindingId}
                    />
                  </div>
                </div>
              </div>
            ) : activeDocument ? (
              // Single Document Viewer Mode
              <div className="h-[620px]">
                <DocumentViewer
                  documentId={activeDocument.id}
                  docType={activeDocument.doc_type}
                  filePath={activeDocument.file_path}
                  initialPage={activePage}
                  highlightBoxes={activeHighlightBoxes}
                  enableElaToggle={
                    activeFinding?.code === 'TAMPER_SUSPECTED' &&
                    activeFinding?.document_id === activeDocument.id
                  }
                  elaHeatmapUrl={activeFinding?.evidence?.heatmap_url}
                  title={DOC_TYPE_LABELS[activeDocument.doc_type] || activeDocument.doc_type}
                  zoomTrigger={selectedFindingId}
                />
              </div>
            ) : (
              <div className="p-16 text-center text-slate-400 text-xs">
                No document selected.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Section: Verifications Table & Handbook Checklist */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
        {/* Navigation Tabs */}
        <div className="flex items-center gap-4 px-5 pt-3 border-b border-slate-200">
          <button
            onClick={() => setBottomTab('verifications')}
            className={`pb-2.5 text-xs font-bold border-b-2 transition-all flex items-center gap-1.5 ${
              bottomTab === 'verifications'
                ? 'border-blue-900 text-blue-900'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Registry Verifications ({app.verifications.length})</span>
          </button>

          <button
            onClick={() => setBottomTab('checklist')}
            className={`pb-2.5 text-xs font-bold border-b-2 transition-all flex items-center gap-1.5 ${
              bottomTab === 'checklist'
                ? 'border-blue-900 text-blue-900'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Handbook Document Checklist</span>
          </button>

          <button
            onClick={() => setBottomTab('fields')}
            className={`pb-2.5 text-xs font-bold border-b-2 transition-all flex items-center gap-1.5 ${
              bottomTab === 'fields'
                ? 'border-blue-900 text-blue-900'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Edit3 className="w-3.5 h-3.5" />
            <span>Extracted Fields &amp; Corrections ({app.fields.length})</span>
          </button>
        </div>

        {/* Tab 1: Verification Table */}
        {bottomTab === 'verifications' && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase font-semibold text-[10px] tracking-wider border-b border-slate-200">
                <tr>
                  <th className="px-5 py-3">Document</th>
                  <th className="px-5 py-3">Verification Source</th>
                  <th className="px-5 py-3">Reference No.</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Comparison Details</th>
                  <th className="px-5 py-3">Checked At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {app.verifications.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-8 text-center text-slate-400">
                      No automated registry checks recorded for this application.
                    </td>
                  </tr>
                ) : (
                  app.verifications.map((v) => {
                    const doc = app.documents.find((d) => d.id === v.document_id);
                    const docLabel = doc ? DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type : 'Application Document';

                    let detailsText = v.details_json || 'Completed';
                    try {
                      const parsed = JSON.parse(v.details_json || '{}');
                      if (parsed.message) {
                        detailsText = parsed.message;
                      } else if (parsed.compared) {
                        detailsText = Object.entries(parsed.compared)
                          .map(([k, val]: [string, any]) => `${k}: ${val.doc} vs ${val.registry}`)
                          .join(', ');
                      }
                    } catch {
                      // ignore json error
                    }

                    return (
                      <tr key={v.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="px-5 py-3 font-semibold text-slate-900">{docLabel}</td>
                        <td className="px-5 py-3 text-slate-700 font-mono text-[11px]">{v.source}</td>
                        <td className="px-5 py-3 text-slate-600 font-mono text-[11px]">{v.reference}</td>
                        <td className="px-5 py-3">{getVerificationStatusChip(v.status)}</td>
                        <td className="px-5 py-3 text-slate-600 max-w-xs truncate" title={detailsText}>
                          {detailsText}
                        </td>
                        <td className="px-5 py-3 text-slate-400 font-mono text-[11px]">
                          {v.checked_at ? formatDateTime(v.checked_at) : 'Recent'}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 2: Handbook Checklist */}
        {bottomTab === 'checklist' && (
          <div className="p-5">
            <div className="mb-3 text-xs text-slate-500 flex items-center justify-between">
              <span>
                Standard document compliance requirements for <strong>{getCategoryLabel(app.category)}</strong> per AICTE Handbook.
              </span>
              <span className="font-mono text-[11px] text-slate-400">
                {app.documents.length} attached items
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {/* Mandatory Documents */}
              {checklistConfig.required.map((reqDocType) => {
                const attached = app.documents.find((d) => d.doc_type === reqDocType);
                return (
                  <div
                    key={reqDocType}
                    className={`p-3.5 rounded-lg border flex items-start justify-between gap-3 text-xs ${
                      attached
                        ? 'bg-emerald-50/40 border-emerald-200'
                        : 'bg-red-50/50 border-red-200'
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-1.5 font-bold text-slate-900">
                        {attached ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                        ) : (
                          <XCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
                        )}
                        <span>{DOC_TYPE_LABELS[reqDocType] || reqDocType}</span>
                      </div>
                      <div className="text-[11px] text-slate-500 mt-1">
                        {attached ? (
                          <span className="text-emerald-700 font-medium">
                            Attached • {attached.scanned ? 'Scanned PDF' : 'Digital PDF'} • {attached.page_count} page(s)
                          </span>
                        ) : (
                          <span className="text-red-700 font-semibold">
                            Mandatory requirement missing
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <span className="text-[10px] uppercase font-bold text-red-700 bg-red-100 px-1.5 py-0.5 rounded">
                        Required
                      </span>
                      {attached && (
                        <button
                          onClick={() => {
                            setIsSideBySide(false);
                            setActiveDocId(attached.id);
                            setActivePage(1);
                            window.scrollTo({ top: 120, behavior: 'smooth' });
                          }}
                          className="text-[10px] font-semibold text-blue-700 hover:underline"
                        >
                          View in Reader
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Optional Documents */}
              {checklistConfig.optional.map((optDocType) => {
                const attached = app.documents.find((d) => d.doc_type === optDocType);
                return (
                  <div
                    key={optDocType}
                    className="p-3.5 rounded-lg border border-slate-200 bg-slate-50/60 flex items-start justify-between gap-3 text-xs"
                  >
                    <div>
                      <div className="flex items-center gap-1.5 font-bold text-slate-800">
                        {attached ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                        ) : (
                          <Info className="w-4 h-4 text-slate-400 flex-shrink-0" />
                        )}
                        <span>{DOC_TYPE_LABELS[optDocType] || optDocType}</span>
                      </div>
                      <div className="text-[11px] text-slate-500 mt-1">
                        {attached ? 'Optional • Attached' : 'Optional • Not submitted'}
                      </div>
                    </div>

                    <span className="text-[10px] uppercase font-bold text-slate-500 bg-slate-200 px-1.5 py-0.5 rounded">
                      Optional
                    </span>
                  </div>
                );
              })}

              {/* Campus Photos */}
              {checklistConfig.photos.map((photoType) => {
                const attached = app.documents.find((d) => d.doc_type === photoType);
                return (
                  <div
                    key={photoType}
                    className={`p-3.5 rounded-lg border flex items-start justify-between gap-3 text-xs ${
                      attached
                        ? 'bg-emerald-50/40 border-emerald-200'
                        : 'bg-amber-50/40 border-amber-200'
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-1.5 font-bold text-slate-900">
                        {attached ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                        ) : (
                          <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                        )}
                        <span>{DOC_TYPE_LABELS[photoType] || photoType}</span>
                      </div>
                      <div className="text-[11px] text-slate-500 mt-1">
                        {attached ? 'Infrastructure photo attached' : 'Photo required'}
                      </div>
                    </div>

                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <span className="text-[10px] uppercase font-bold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">
                        Photo
                      </span>
                      {attached && (
                        <button
                          onClick={() => {
                            setIsSideBySide(false);
                            setActiveDocId(attached.id);
                            window.scrollTo({ top: 120, behavior: 'smooth' });
                          }}
                          className="text-[10px] font-semibold text-blue-700 hover:underline"
                        >
                          View Photo
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Tab 3: Extracted Fields & Human Corrections */}
        {bottomTab === 'fields' && (
          <div className="p-4 space-y-4">
            <div className="flex items-center justify-between text-xs text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-200">
              <div>
                <span className="font-semibold text-slate-800">Field Extraction &amp; Correction Gate</span>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Fields with low OCR confidence or unreadable values can be manually transcribed by the scrutiny officer.
                  Correcting a field updates the dossier to 100% human confidence, resolves low-confidence findings, and writes an immutable audit record.
                </p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 uppercase font-semibold text-[10px] tracking-wider border-b border-slate-200">
                  <tr>
                    <th className="px-4 py-3">Document / Scope</th>
                    <th className="px-4 py-3">Field Name</th>
                    <th className="px-4 py-3">Extracted Value</th>
                    <th className="px-4 py-3">Confidence</th>
                    <th className="px-4 py-3 text-right">Human Review &amp; Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {app.fields.map((field) => {
                    const doc = app.documents.find((d) => d.id === field.document_id);
                    const isUnreadable =
                      field.value === null ||
                      field.value === 'null' ||
                      field.value === '' ||
                      (field.confidence ?? 0) < 0.6;
                    const isEditing = editingFieldId === field.id;
                    const currentValue =
                      editValues[field.id] !== undefined
                        ? editValues[field.id]
                        : field.value === 'null' || field.value === null
                        ? ''
                        : field.value;

                    return (
                      <tr key={field.id} className={`hover:bg-slate-50/80 transition-colors ${isUnreadable ? 'bg-amber-50/30' : ''}`}>
                        <td className="px-4 py-3 align-top font-medium text-slate-800">
                          <div>{doc ? DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type : `Doc #${field.document_id}`}</div>
                          <div className="text-[10px] text-slate-400 font-mono">Page {field.page || 1}</div>
                        </td>
                        <td className="px-4 py-3 align-top font-mono font-medium text-slate-700">
                          {field.field_name || field.name || 'field'}
                        </td>
                        <td className="px-4 py-3 align-top font-mono">
                          {isEditing ? (
                            <div className="space-y-1.5 max-w-sm">
                              <input
                                type="text"
                                value={currentValue}
                                onChange={(e) =>
                                  setEditValues({ ...editValues, [field.id]: e.target.value })
                                }
                                placeholder="Enter verified human value..."
                                className="w-full px-2.5 py-1.5 text-xs border border-blue-400 rounded focus:ring-1 focus:ring-blue-500 bg-white"
                              />
                              <input
                                type="text"
                                value={editComments[field.id] || ''}
                                onChange={(e) =>
                                  setEditComments({ ...editComments, [field.id]: e.target.value })
                                }
                                placeholder="Audit note / reason for correction..."
                                className="w-full px-2 py-1 text-[11px] border border-slate-300 rounded bg-white text-slate-600"
                              />
                            </div>
                          ) : (
                            <div className="flex items-center gap-2">
                              {isUnreadable ? (
                                <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-800 border border-amber-300 flex items-center gap-1">
                                  <AlertTriangle className="w-3 h-3 text-amber-600" />
                                  {field.value === 'null' || !field.value ? 'Unreadable / Missing' : field.value}
                                </span>
                              ) : (
                                <span className="text-slate-900 font-semibold">{field.value}</span>
                              )}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3 align-top">
                          {field.confidence === 1.0 ? (
                            <span className="text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded text-[10px] font-bold">
                              100% (Human Verified)
                            </span>
                          ) : (field.confidence ?? 0) >= 0.7 ? (
                            <span className="text-slate-700 text-[11px]">
                              {Math.round((field.confidence ?? 0) * 100)}%
                            </span>
                          ) : (
                            <span className="text-red-700 bg-red-50 border border-red-200 px-2 py-0.5 rounded text-[10px] font-bold">
                              {Math.round((field.confidence ?? 0) * 100)}% (Low OCR)
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 align-top text-right">
                          {isEditing ? (
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => handleSaveCorrection(field.id)}
                                disabled={savingFieldId === field.id}
                                className="px-3 py-1 bg-emerald-700 hover:bg-emerald-800 text-white rounded text-xs font-semibold flex items-center gap-1 shadow-xs"
                              >
                                <Save className="w-3.5 h-3.5" />
                                <span>{savingFieldId === field.id ? 'Saving...' : 'Save'}</span>
                              </button>
                              <button
                                onClick={() => setEditingFieldId(null)}
                                className="px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-xs"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => {
                                setEditingFieldId(field.id);
                                if (editValues[field.id] === undefined) {
                                  setEditValues({
                                    ...editValues,
                                    [field.id]: field.value === 'null' || !field.value ? '' : field.value,
                                  });
                                }
                              }}
                              className={`px-2.5 py-1 rounded text-xs font-semibold border flex items-center gap-1 ml-auto transition-colors ${
                                isUnreadable
                                  ? 'bg-blue-900 text-white border-blue-900 hover:bg-blue-800'
                                  : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                              }`}
                            >
                              <Edit3 className="w-3 h-3" />
                              <span>{isUnreadable ? 'Resolve Unreadable' : 'Correct Value'}</span>
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </>
  )}

      {/* Advisory Notice Disclaimer */}
      <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-center text-xs text-slate-500">
        AI findings are advisory. Final decisions rest with competent AICTE authorities.
      </div>
    </div>
  );
};

export const ApplicationDetailPlaceholder = ApplicationDetail;

