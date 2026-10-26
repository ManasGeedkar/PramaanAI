import React, { useState } from 'react';
import { Sidebar, type UserRole } from './components/Sidebar';
import { Footer } from './components/Footer';
import { TriageQueue } from './pages/TriageQueue';
import { Overview } from './pages/Overview';
import { ApplicationDetail } from './pages/ApplicationDetail';
import { AuditLogPage } from './pages/AuditLogPage';
import { EvaluationPage } from './pages/EvaluationPage';
import { RulesAdminPage } from './pages/RulesAdminPage';
import { NewApplicationPage } from './pages/NewApplicationPage';
import { ShieldCheck } from 'lucide-react';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<string>('queue');
  const [selectedAppId, setSelectedAppId] = useState<number | null>(null);

  // Store role in localStorage (default to Scrutiny Officer)
  const [role, setRole] = useState<UserRole>(() => {
    const saved = localStorage.getItem('pramaan_role');
    if (saved === 'Institution' || saved === 'Admin' || saved === 'Scrutiny Officer') {
      return saved;
    }
    return 'Scrutiny Officer';
  });

  const handleRoleChange = (newRole: UserRole) => {
    setRole(newRole);
    localStorage.setItem('pramaan_role', newRole);
    // If switching to institution and currently on admin-only page, switch to upload or overview
    if (newRole === 'Institution' && (currentTab === 'rules' || currentTab === 'queue')) {
      setCurrentTab('upload');
    }
  };

  const handleSelectApplication = (id: number) => {
    setSelectedAppId(id);
  };

  const handleBackToQueue = () => {
    setSelectedAppId(null);
  };

  const handleTabChange = (tab: string) => {
    setCurrentTab(tab);
    setSelectedAppId(null); // Reset detail view when navigating
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-100 font-sans">
      {/* Left Sidebar */}
      <Sidebar
        currentTab={selectedAppId ? 'queue' : currentTab}
        onTabChange={handleTabChange}
        role={role}
        onRoleChange={handleRoleChange}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Top Header Bar */}
        <header className="h-14 bg-white border-b border-slate-200 px-6 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
              {role} Console
            </span>
            <span className="text-slate-300">•</span>
            <span className="text-xs font-semibold text-blue-900 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-200">
              {selectedAppId
                ? 'Application Detail Scrutiny'
                : currentTab === 'queue'
                ? 'Triage Queue'
                : currentTab === 'upload'
                ? 'New Application Dossier'
                : currentTab === 'overview'
                ? 'Management View'
                : currentTab === 'evaluate'
                ? 'Benchmark Evaluation'
                : currentTab === 'audit'
                ? 'Audit Log'
                : 'Rules Engine'}
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5 text-slate-500 font-medium">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Pre-scrutiny engine: <strong>Active</strong></span>
            </div>
            <div className="w-8 h-8 rounded-full bg-slate-100 text-slate-600 flex items-center justify-center font-bold text-xs border border-slate-200">
              {role === 'Scrutiny Officer' ? 'SO' : role === 'Institution' ? 'IN' : 'AD'}
            </div>
          </div>
        </header>

        {/* Scrollable Main View Container */}
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            {selectedAppId ? (
              <ApplicationDetail
                applicationId={selectedAppId}
                onBack={handleBackToQueue}
              />
            ) : currentTab === 'queue' ? (
              <TriageQueue onSelectApplication={handleSelectApplication} />
            ) : currentTab === 'upload' ? (
              <NewApplicationPage onOpenApplication={handleSelectApplication} />
            ) : currentTab === 'overview' ? (
              <Overview />
            ) : currentTab === 'evaluate' ? (
              <EvaluationPage />
            ) : currentTab === 'audit' ? (
              <AuditLogPage />
            ) : currentTab === 'rules' ? (
              <RulesAdminPage />
            ) : (
              <TriageQueue onSelectApplication={handleSelectApplication} />
            )}
          </div>
        </main>

        {/* Mandatory Footer */}
        <Footer />
      </div>
    </div>
  );
};

export default App;
