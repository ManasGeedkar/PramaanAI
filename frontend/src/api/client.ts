import type {
  ApplicationQueueItem,
  ApplicationDetail,
  SystemStats,
  ReviewResponse,
  EvaluationResult,
  AuditLogItem,
  AuditVerifyResult,
} from './types';

const BASE_URL = '';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const errJson = await res.json();
      errorDetail = errJson.detail || JSON.stringify(errJson);
    } catch {
      // ignore
    }
    throw new Error(`API Error (${res.status}): ${errorDetail}`);
  }

  return res.json();
}

export const api = {
  // Queue & Applications
  getApplications: async (sort: string = 'risk'): Promise<ApplicationQueueItem[]> => {
    return fetchJson<ApplicationQueueItem[]>(`/api/applications?sort=${encodeURIComponent(sort)}`);
  },

  getApplication: async (id: number | string): Promise<ApplicationDetail> => {
    return fetchJson<ApplicationDetail>(`/api/applications/${id}`);
  },

  runApplicationPipeline: async (id: number | string): Promise<any> => {
    return fetchJson<any>(`/api/applications/${id}/run`, { method: 'POST' });
  },

  getBriefPdfUrl: (id: number | string): string => {
    return `/api/applications/${id}/brief.pdf`;
  },

  getDocumentFileUrl: (id: number): string => {
    return `/api/documents/${id}/file`;
  },

  getDocumentElaUrl: (id: number): string => {
    return `/api/documents/${id}/ela.png`;
  },

  // Reviews
  reviewFinding: async (
    findingId: number,
    decision: 'accept' | 'dismiss' | 'request_evidence' | 'escalate',
    comment?: string,
    reviewer: string = 'Scrutiny Officer'
  ): Promise<ReviewResponse> => {
    return fetchJson<ReviewResponse>(`/api/findings/${findingId}/review`, {
      method: 'POST',
      body: JSON.stringify({ decision, comment, reviewer }),
    });
  },

  // Stats & Dashboard
  getStats: async (): Promise<SystemStats> => {
    return fetchJson<SystemStats>('/api/stats');
  },

  // Evaluation
  getEvaluation: async (): Promise<EvaluationResult> => {
    return fetchJson<EvaluationResult>('/api/evaluate');
  },

  // Audit
  getAuditLogs: async (entityId?: string, applicationId?: string): Promise<AuditLogItem[]> => {
    const params = new URLSearchParams();
    if (entityId) params.append('entity_id', entityId);
    if (applicationId && applicationId !== 'all') params.append('application_id', applicationId);
    const q = params.toString() ? `?${params.toString()}` : '';
    return fetchJson<AuditLogItem[]>(`/api/audit${q}`);
  },

  verifyAuditChain: async (): Promise<AuditVerifyResult> => {
    return fetchJson<AuditVerifyResult>('/api/audit/verify');
  },

  // Rules
  getRules: async (): Promise<{ version: string; yaml_text: string; rules: any[] }> => {
    return fetchJson<{ version: string; yaml_text: string; rules: any[] }>('/api/rules');
  },

  updateRules: async (yamlText: string): Promise<any> => {
    return fetchJson<any>('/api/rules', {
      method: 'PUT',
      body: JSON.stringify({ yaml_text: yamlText }),
    });
  },

  // Entity Graph
  getEntityGraph: async (applicationId?: number): Promise<any> => {
    const q = applicationId ? `?application_id=${applicationId}` : '';
    return fetchJson<any>(`/api/entities/graph${q}`);
  },

  // Quality check
  checkQuality: async (file: File): Promise<{
    filename: string;
    is_clear: boolean;
    blur_variance: number;
    effective_dpi: number;
    reason: string | null;
    warning: string | null;
  }> => {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/api/quality-check', {
      method: 'POST',
      body: fd,
    });
    if (!res.ok) {
      throw new Error(`Quality check failed: ${res.statusText}`);
    }
    return res.json();
  },

  // Human correction for unreadable / low confidence fields
  correctField: async (
    fieldId: number,
    value: string,
    comment?: string
  ): Promise<{ success: boolean; field: any; message: string }> => {
    return fetchJson<{ success: boolean; field: any; message: string }>(`/api/fields/${fieldId}/correct`, {
      method: 'POST',
      body: JSON.stringify({ value, comment }),
    });
  },

  // Samples
  getSamples: async (): Promise<
    Array<{
      folder: string;
      institution_name: string;
      institution_id?: string;
      aicte_id: string;
      category: string;
      academic_year?: string;
      programmes?: any[];
      declared?: Record<string, any>;
      declared_values?: Record<string, any>;
      documents?: Array<{ doc_type: string; file: string; path?: string }>;
      photos?: Array<{ type: string; file: string }>;
    }>
  > => {
    return fetchJson('/api/samples');
  },

  // Sample Upload
  uploadSample: async (folder: string): Promise<{ id: number; application_no: string; status: string }> => {
    return fetchJson<{ id: number; application_no: string; status: string }>('/api/applications/upload-sample', {
      method: 'POST',
      body: JSON.stringify({ folder }),
    });
  },

  // Live Upload
  uploadApplication: async (
    formData: FormData
  ): Promise<{ id: number; application_no: string; status: string }> => {
    const res = await fetch('/api/applications/upload', {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      let errDetail = res.statusText;
      try {
        const errJson = await res.json();
        errDetail = errJson.detail || JSON.stringify(errJson);
      } catch {
        // ignore
      }
      throw new Error(`Upload failed: ${errDetail}`);
    }
    return res.json();
  },
};
