// Data contracts matching BUILD_GUIDE.md Section 4

export type RiskBand = 'High' | 'Medium' | 'Low';

export type ApplicationStatus =
  | 'processing'
  | 'validated'
  | 'under_review'
  | 'evidence_requested'
  | 'escalated'
  | 'closed';

export type FindingSeverity = 'critical' | 'warning' | 'info';

export type FindingStatus =
  | 'open'
  | 'accepted'
  | 'dismissed'
  | 'evidence_requested'
  | 'escalated';

export type VerificationStatus =
  | 'verified'
  | 'mismatch'
  | 'expired'
  | 'pending'
  | 'source_unavailable'
  | 'manual_review';

export interface RiskBreakdownItem {
  reason: string;
  points: number;
  finding_id: number | null;
}

export interface ApplicationQueueItem {
  id: number;
  no?: string;
  application_no?: string;
  institution_id?: string;
  institution?: string;
  institution_name?: string;
  category: string;
  status: ApplicationStatus;
  risk_band: RiskBand;
  risk_score: number;
  counts: {
    critical: number;
    warning: number;
    info: number;
  };
  submitted_on?: string;
  academic_year?: string;
  risk_breakdown?: RiskBreakdownItem[];
}

export interface DocumentItem {
  id: number;
  application_id: number;
  doc_type: string;
  file_path: string;
  sha256: string;
  scanned: boolean;
  page_count: number;
  producer?: string | null;
  creation_date?: string | null;
  mod_date?: string | null;
  ocr_confidence?: number | null;
}

export interface ExtractedFieldItem {
  id: number;
  document_id: number;
  name?: string;
  field_name?: string;
  value: string | null;
  page: number;
  bbox_json: string | null;
  confidence: number | null;
}

export interface EvidenceItem {
  document_id?: number;
  doc_type?: string;
  page?: number;
  bbox?: [number, number, number, number];
  field?: string;
  value?: string;
}

export interface FindingEvidence {
  items?: EvidenceItem[];
  expected?: string;
  method?: string;
  related_applications?: string[];
  heatmap_url?: string | null;
  explanation?: string;
}

export interface FindingItem {
  id: number;
  application_id: number;
  document_id: number | null;
  code: string;
  severity: FindingSeverity;
  title: string;
  message: string;
  rule_id: string | null;
  evidence: FindingEvidence | null;
  confidence: number | null;
  status: FindingStatus;
  created_at: string;
}

export interface VerificationItem {
  id: number;
  document_id: number;
  source: string;
  reference: string;
  status: VerificationStatus;
  details_json: string | null;
  checked_at: string;
}

export interface ApplicationDetail {
  id: number;
  application_no: string;
  institution_id: string;
  institution_name: string;
  aicte_id: string;
  category: string;
  academic_year: string;
  submitted_on: string;
  status: ApplicationStatus;
  risk_band: RiskBand;
  risk_score: number;
  risk_breakdown: RiskBreakdownItem[];
  folder: string;
  created_at: string;
  documents: DocumentItem[];
  fields: ExtractedFieldItem[];
  findings: FindingItem[];
  verifications: VerificationItem[];
}

export interface SystemStats {
  total_applications: number;
  high_risk_count: number;
  by_band: {
    High: number;
    Medium: number;
    Low: number;
  };
  by_verification_status: Record<VerificationStatus, number>;
  total_documents: number;
  documents_auto_cleared: number;
  flagged_findings_count: number;
  hours_saved: number;
  hours_saved_assumption: string;
}

export interface ReviewResponse {
  ok: boolean;
  finding: {
    id: number;
    code: string;
    status: FindingStatus;
  };
  application: {
    id: number;
    status: ApplicationStatus;
    risk_score: number;
    risk_band: RiskBand;
    risk_breakdown: RiskBreakdownItem[];
  };
  review: {
    id: number;
    reviewer: string;
    decision: string;
    comment?: string;
  };
}

export interface EvaluationResult {
  extraction_accuracy: number;
  verification_accuracy: number;
  finding_recall: number;
  total_expected_findings: number;
  matched_findings_count: number;
  false_positives_count: number;
  risk_band_accuracy: number;
  average_pipeline_seconds: number;
  applications: Array<{
    institution_id: string;
    application_no: string;
    actual_risk_band: RiskBand;
    expected_risk_band: RiskBand;
    risk_band_matched: boolean;
    risk_score: number;
    total_expected: number;
    matched_count: number;
    expected_findings: any[];
    extra_findings: any[];
  }>;
}

export interface AuditLogItem {
  id: number;
  ts: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  payload_json: string | null;
  prev_hash: string;
  hash: string;
}

export interface AuditVerifyResult {
  ok: boolean;
  broken_at: number | null;
}
