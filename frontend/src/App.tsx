import React, { useState } from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  Outlet,
  useLocation,
  useNavigate,
} from 'react-router-dom';
import { Sidebar, type UserRole } from './components/Sidebar';
import { Footer } from './components/Footer';
import { LoginPage } from './pages/LoginPage';
import { TriageQueue } from './pages/TriageQueue';
import { Overview } from './pages/Overview';
import { ApplicationDetail } from './pages/ApplicationDetail';
import { AuditLogPage } from './pages/AuditLogPage';
import { EvaluationPage } from './pages/EvaluationPage';
import { RulesAdminPage } from './pages/RulesAdminPage';
import { NewApplicationPage } from './pages/NewApplicationPage';
import { ShieldCheck } from 'lucide-react';

export const getRoleHome = (role: UserRole | null | string): string => {
  if (role === 'Institution') return '/new';
  if (role === 'Admin') return '/admin/rules';
  if (role === 'Scrutiny Officer') return '/queue';
  return '/login';
};

export const getStoredRole = (): UserRole | null => {
  const saved = localStorage.getItem('pramaan_role');
  if (saved === 'Scrutiny Officer' || saved === 'Institution' || saved === 'Admin') {
    return saved;
  }
  return null;
};

// Root index redirect handler: / -> role's home or /login
const RootRedirect: React.FC = () => {
  const role = getStoredRole();
  if (role) {
    return <Navigate to={getRoleHome(role)} replace />;
  }
  return <Navigate to="/login" replace />;
};

// Protected Dashboard Layout with Sidebar & Header
interface DashboardLayoutProps {
  role: UserRole | null;
  onRoleChange: (newRole: UserRole) => void;
  onSignOut: () => void;
}

const DashboardLayout: React.FC<DashboardLayoutProps> = ({
  role,
  onRoleChange,
  onSignOut,
}) => {
  const location = useLocation();

  // If no role stored, redirect to /login
  if (!role) {
    return <Navigate to="/login" replace />;
  }

  // Derive page title for header bar based on current pathname
  const getHeaderTitle = () => {
    const path = location.pathname;
    if (path.startsWith('/applications')) return 'Application Detail Scrutiny';
    if (path === '/queue') return 'Triage Queue';
    if (path === '/new') return 'New Application Dossier';
    if (path === '/overview') return 'Management View';
    if (path === '/evaluation') return 'Benchmark Evaluation';
    if (path === '/audit') return 'Audit Log';
    if (path === '/admin/rules') return 'Rules Engine';
    return 'Scrutiny Portal';
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-100 font-sans">
      {/* Left Sidebar */}
      <Sidebar
        role={role}
        onRoleChange={onRoleChange}
        onSignOut={onSignOut}
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
              {getHeaderTitle()}
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
            <Outlet />
          </div>
        </main>

        {/* Mandatory Footer */}
        <Footer />
      </div>
    </div>
  );
};

// Login Route Container
const LoginRoute: React.FC<{ onLogin: (selectedRole: UserRole) => void }> = ({ onLogin }) => {
  return <LoginPage onSelectRole={onLogin} />;
};

const AppContent: React.FC = () => {
  const [role, setRole] = useState<UserRole | null>(getStoredRole);
  const navigate = useNavigate();

  const handleLogin = (selectedRole: UserRole) => {
    localStorage.setItem('pramaan_role', selectedRole);
    setRole(selectedRole);
    navigate(getRoleHome(selectedRole), { replace: true });
  };

  const handleRoleChange = (newRole: UserRole) => {
    localStorage.setItem('pramaan_role', newRole);
    setRole(newRole);

    // If switching to institution and currently on admin-only page or queue, switch to new
    const path = window.location.pathname;
    if (newRole === 'Institution' && (path === '/admin/rules' || path === '/queue' || path === '/audit' || path === '/evaluation')) {
      navigate('/new');
    }
  };

  const handleSignOut = () => {
    localStorage.removeItem('pramaan_role');
    setRole(null);
    navigate('/login', { replace: true });
  };

  return (
    <Routes>
      {/* Entry Route: /login */}
      <Route path="/login" element={<LoginRoute onLogin={handleLogin} />} />

      {/* Root redirect: / -> role's home or /login */}
      <Route path="/" element={<RootRedirect />} />

      {/* Protected Layout & Pages */}
      <Route
        element={
          <DashboardLayout
            role={role}
            onRoleChange={handleRoleChange}
            onSignOut={handleSignOut}
          />
        }
      >
        <Route path="/queue" element={<TriageQueue />} />
        <Route path="/applications/:id" element={<ApplicationDetail />} />
        <Route path="/new" element={<NewApplicationPage />} />
        <Route path="/overview" element={<Overview />} />
        <Route path="/evaluation" element={<EvaluationPage />} />
        <Route path="/audit" element={<AuditLogPage />} />
        <Route path="/admin/rules" element={<RulesAdminPage />} />
      </Route>

      {/* Catch-all: redirect to / */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
};

export default App;
