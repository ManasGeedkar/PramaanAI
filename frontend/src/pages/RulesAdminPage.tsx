import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import {
  Save,
  CheckCircle2,
  Code2,
  Sliders,
  Flame,
  FileText,
  Users,
  Building,
  GraduationCap,
  Sparkles,
} from 'lucide-react';

export const RulesAdminPage: React.FC = () => {
  const [yamlText, setYamlText] = useState<string>('');
  const [version, setVersion] = useState<string>('2027-28.v1');
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'cards' | 'yaml'>('cards');

  // Editable parameters parsed from yaml
  const [params, setParams] = useState<Record<string, any>>({
    min_land_acres: 2.5,
    faculty_student_ratio: 20,
    min_built_up_sqm_per_seat: 40,
    session_start: '2027-07-01',
  });

  const fetchRules = async () => {
    try {
      setLoading(true);
      const data = await api.getRules();
      setYamlText(data.yaml_text || '');
      setVersion(data.version || '2027-28.v1');

      // Extract params from YAML text
      extractParamsFromYaml(data.yaml_text || '');
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const extractParamsFromYaml = (text: string) => {
    try {
      const minLandMatch = text.match(/min_land_acres:\s*([0-9.]+)/);
      const fsrMatch = text.match(/faculty_student_ratio:\s*([0-9]+)/);
      const buaMatch = text.match(/min_built_up_sqm_per_seat:\s*([0-9]+)/);
      const sessionMatch = text.match(/session_start:\s*["']?([^"'\n]+)["']?/);

      setParams({
        min_land_acres: minLandMatch ? parseFloat(minLandMatch[1]) : 2.5,
        faculty_student_ratio: fsrMatch ? parseInt(fsrMatch[1]) : 20,
        min_built_up_sqm_per_seat: buaMatch ? parseInt(buaMatch[1]) : 40,
        session_start: sessionMatch ? sessionMatch[1].trim() : '2027-07-01',
      });
    } catch {
      // fallback
    }
  };

  const updateYamlWithParams = (newParams: Record<string, any>) => {
    let updated = yamlText;
    if (newParams.min_land_acres !== undefined) {
      updated = updated.replace(/min_land_acres:\s*[0-9.]+/, `min_land_acres: ${newParams.min_land_acres}`);
    }
    if (newParams.faculty_student_ratio !== undefined) {
      updated = updated.replace(/faculty_student_ratio:\s*[0-9]+/, `faculty_student_ratio: ${newParams.faculty_student_ratio}`);
    }
    if (newParams.min_built_up_sqm_per_seat !== undefined) {
      updated = updated.replace(
        /min_built_up_sqm_per_seat:\s*[0-9]+/,
        `min_built_up_sqm_per_seat: ${newParams.min_built_up_sqm_per_seat}`
      );
    }
    if (newParams.session_start !== undefined) {
      updated = updated.replace(/session_start:\s*["']?[^"'\n]+["']?/, `session_start: "${newParams.session_start}"`);
    }
    setYamlText(updated);
    setParams(newParams);
  };

  const handleParamChange = (key: string, val: any) => {
    const newParams = { ...params, [key]: val };
    updateYamlWithParams(newParams);
  };

  const handleSaveAndReRun = async () => {
    try {
      setSaving(true);
      setToastMessage(null);
      const res = await api.updateRules(yamlText);

      // Analyze changed counts
      const changed = res.changed_counts || {};
      const affectedInsts = Object.entries(changed)
        .filter(([_, delta]) => delta !== 0)
        .map(([inst, delta]) => `${inst} (${(delta as number) > 0 ? '+' : ''}${delta})`);

      const affectedCount = affectedInsts.length;
      let toast = '';
      if (affectedCount > 0) {
        toast = `Rules updated: ${affectedCount} application(s) affected: ${affectedInsts.join(', ')}`;
      } else {
        toast = `Rules updated successfully (v${res.version}). No applications changed findings.`;
      }

      setToastMessage(toast);
    } catch (err: any) {
      alert(`Save failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    fetchRules();
  }, []);

  const ruleCards = [
    {
      id: 'R-LAND-001',
      title: 'Minimum Land Area Norm',
      category: 'Campus Infrastructure',
      severity: 'critical',
      docType: 'Land / Sale Deed',
      field: 'land_area_acres',
      paramKey: 'min_land_acres',
      paramLabel: 'Min Land Area (Acres)',
      description:
        'Validates that land area per registered sale/lease deed meets minimum AICTE norms. (INST05 declared 2.00 acres; lowering to 1.5 acres resolves the finding).',
      icon: <Building className="w-5 h-5 text-indigo-600" />,
    },
    {
      id: 'R-FIRE-001',
      title: 'Fire Safety NOC Expiry Check',
      category: 'Statutory Safety',
      severity: 'critical',
      docType: 'Fire Safety NOC',
      field: 'valid_till',
      paramKey: 'session_start',
      paramLabel: 'Session Start Date',
      description:
        'Requires Fire Safety NOC to be valid on or beyond the commencement of the academic session.',
      icon: <Flame className="w-5 h-5 text-red-600" />,
    },
    {
      id: 'R-FAC-001',
      title: 'Cadre & Faculty-to-Student Ratio',
      category: 'Academic Faculty',
      severity: 'critical',
      docType: 'Faculty List',
      field: 'faculty_count',
      paramKey: 'faculty_student_ratio',
      paramLabel: 'Ratio (Students : Faculty)',
      description:
        'Verifies that declared faculty count satisfies ceiling ratio based on proposed intake.',
      icon: <Users className="w-5 h-5 text-blue-600" />,
    },
    {
      id: 'R-BUA-001',
      title: 'Built-up Area per Sanctioned Seat',
      category: 'Campus Infrastructure',
      severity: 'warning',
      docType: 'Building Plan / Fire NOC',
      field: 'built_up_area_sqm',
      paramKey: 'min_built_up_sqm_per_seat',
      paramLabel: 'Min Built-up Area (Sq. m / seat)',
      description:
        'Ensures instructional and administrative space accommodates the requested student intake.',
      icon: <FileText className="w-5 h-5 text-amber-600" />,
    },
    {
      id: 'R-ACC-001',
      title: 'Mandatory NBA/NAAC Accreditation for Expansion',
      category: 'Quality Assurance',
      severity: 'critical',
      docType: 'Accreditation Certificate',
      field: 'valid_till',
      paramKey: 'session_start',
      paramLabel: 'Session Start Date',
      description:
        'Institutions requesting intake increase must hold valid accreditation through session start.',
      icon: <GraduationCap className="w-5 h-5 text-emerald-600" />,
    },
  ];

  return (
    <div className="space-y-4">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="bg-emerald-50 border border-emerald-300 text-emerald-900 px-4 py-3 rounded-lg text-xs font-semibold flex items-center justify-between shadow-xs animate-in fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>{toastMessage}</span>
          </div>
          <button
            onClick={() => setToastMessage(null)}
            className="text-emerald-700 hover:text-emerald-900 font-bold"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Header */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Rules Engine &amp; Policy Administration
            </h1>
            <span className="px-2.5 py-0.5 rounded bg-blue-100 text-blue-900 font-mono text-xs font-bold border border-blue-200">
              {version}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl">
            Declarative JSON-Logic rule sets governing AICTE scrutiny compliance. Modifying policy parameters takes effect immediately across all pending and evaluated dossiers without code deployment.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={handleSaveAndReRun}
            disabled={saving || loading}
            className="flex items-center gap-2 px-4 py-2 text-xs font-bold text-white bg-blue-900 hover:bg-blue-800 rounded-lg shadow-xs transition-colors"
          >
            <Save className={`w-4 h-4 ${saving ? 'animate-spin' : ''}`} />
            <span>{saving ? 'Evaluating Applications...' : 'Save & Re-run All'}</span>
          </button>
        </div>
      </div>

      {/* View Switcher Tabs */}
      <div className="flex items-center gap-2 bg-white p-1 rounded-lg border border-slate-200 w-fit">
        <button
          onClick={() => setActiveTab('cards')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
            activeTab === 'cards'
              ? 'bg-blue-900 text-white shadow-xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <Sliders className="w-3.5 h-3.5" />
          <span>Editable Parameter Cards</span>
        </button>
        <button
          onClick={() => setActiveTab('yaml')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
            activeTab === 'yaml'
              ? 'bg-blue-900 text-white shadow-xs'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          <Code2 className="w-3.5 h-3.5" />
          <span>YAML Editor</span>
        </button>
      </div>

      {/* Tab 1: Cards View */}
      {activeTab === 'cards' && (
        <div className="space-y-4">
          {/* Quick Param Tuner Card */}
          <div className="bg-gradient-to-r from-blue-900 to-indigo-900 text-white p-5 rounded-xl shadow-xs">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-4 h-4 text-amber-300" />
              <h2 className="text-sm font-bold tracking-tight">
                Live Regulatory Thresholds
              </h2>
            </div>
            <p className="text-xs text-blue-200 mb-4 max-w-xl">
              Adjust institutional requirements below. Example demo step: change <strong>Min Land Area</strong> from <strong>2.5</strong> to <strong>1.5</strong> acres, then click <em>Save &amp; Re-run</em> to observe INST05 compliance clearing automatically.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white/10 backdrop-blur-xs p-3 rounded-lg border border-white/20">
                <label className="text-[11px] font-semibold text-blue-200 block mb-1">
                  Min Land Area (Acres)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={params.min_land_acres}
                  onChange={(e) => handleParamChange('min_land_acres', parseFloat(e.target.value) || 0)}
                  className="w-full px-2.5 py-1.5 text-xs font-mono font-bold bg-white text-slate-900 rounded border-none focus:ring-2 focus:ring-amber-400"
                />
                <span className="text-[10px] text-blue-300 block mt-1">Default: 2.5 acres</span>
              </div>

              <div className="bg-white/10 backdrop-blur-xs p-3 rounded-lg border border-white/20">
                <label className="text-[11px] font-semibold text-blue-200 block mb-1">
                  Faculty-to-Student Ratio
                </label>
                <input
                  type="number"
                  value={params.faculty_student_ratio}
                  onChange={(e) => handleParamChange('faculty_student_ratio', parseInt(e.target.value) || 20)}
                  className="w-full px-2.5 py-1.5 text-xs font-mono font-bold bg-white text-slate-900 rounded border-none focus:ring-2 focus:ring-amber-400"
                />
                <span className="text-[10px] text-blue-300 block mt-1">1 teacher per X students</span>
              </div>

              <div className="bg-white/10 backdrop-blur-xs p-3 rounded-lg border border-white/20">
                <label className="text-[11px] font-semibold text-blue-200 block mb-1">
                  Min Built-up Area (Sq. m / seat)
                </label>
                <input
                  type="number"
                  value={params.min_built_up_sqm_per_seat}
                  onChange={(e) =>
                    handleParamChange('min_built_up_sqm_per_seat', parseInt(e.target.value) || 40)
                  }
                  className="w-full px-2.5 py-1.5 text-xs font-mono font-bold bg-white text-slate-900 rounded border-none focus:ring-2 focus:ring-amber-400"
                />
                <span className="text-[10px] text-blue-300 block mt-1">Norm: 40 sq.m / sanctioned seat</span>
              </div>

              <div className="bg-white/10 backdrop-blur-xs p-3 rounded-lg border border-white/20">
                <label className="text-[11px] font-semibold text-blue-200 block mb-1">
                  Academic Session Start
                </label>
                <input
                  type="date"
                  value={params.session_start}
                  onChange={(e) => handleParamChange('session_start', e.target.value)}
                  className="w-full px-2.5 py-1.5 text-xs font-mono font-bold bg-white text-slate-900 rounded border-none focus:ring-2 focus:ring-amber-400"
                />
                <span className="text-[10px] text-blue-300 block mt-1">Cutoff for NOC &amp; validity</span>
              </div>
            </div>
          </div>

          {/* Rule Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {ruleCards.map((rule) => {
              const currentVal = params[rule.paramKey];
              return (
                <div
                  key={rule.id}
                  className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs flex flex-col justify-between hover:border-slate-300 transition-colors"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="p-2 rounded-lg bg-slate-100">{rule.icon}</span>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-bold text-slate-900">
                              {rule.id}
                            </span>
                            <span
                              className={`text-[10px] uppercase font-bold px-1.5 py-0.2 rounded ${
                                rule.severity === 'critical'
                                  ? 'bg-red-100 text-red-800'
                                  : 'bg-amber-100 text-amber-800'
                              }`}
                            >
                              {rule.severity}
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-400">{rule.category}</div>
                        </div>
                      </div>
                    </div>

                    <h3 className="font-bold text-sm text-slate-900 mb-1">{rule.title}</h3>
                    <p className="text-xs text-slate-600 leading-relaxed mb-3">
                      {rule.description}
                    </p>

                    <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-[11px] text-slate-600 space-y-1 mb-4 font-mono">
                      <div>
                        <span className="text-slate-400">Target Document:</span> {rule.docType}
                      </div>
                      <div>
                        <span className="text-slate-400">Evaluated Field:</span> {rule.field}
                      </div>
                    </div>
                  </div>

                  <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                    <span className="text-slate-500 font-medium">{rule.paramLabel}:</span>
                    <span className="font-mono font-bold text-primary-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                      {currentVal}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab 2: YAML Editor */}
      {activeTab === 'yaml' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
          <div className="p-3 bg-slate-900 text-slate-300 text-xs font-mono flex items-center justify-between border-b border-slate-800">
            <span className="flex items-center gap-1.5">
              <Code2 className="w-4 h-4 text-blue-400" />
              <span>data/config/rules.yaml</span>
            </span>
            <span className="text-[11px] text-slate-400">Raw declarative JSON-Logic schema</span>
          </div>
          <textarea
            value={yamlText}
            onChange={(e) => {
              setYamlText(e.target.value);
              extractParamsFromYaml(e.target.value);
            }}
            rows={26}
            className="w-full p-4 font-mono text-xs bg-slate-950 text-slate-200 border-none focus:outline-none resize-none leading-relaxed"
            spellCheck={false}
          />
        </div>
      )}

      {/* Advisory Footer */}
      <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-center text-xs text-slate-500">
        AI findings are advisory. Final decisions rest with competent AICTE authorities.
      </div>
    </div>
  );
};
