import React from 'react';
import {
  FileSearch,
  ShieldCheck,
  UserCheck,
  Building2,
  Sliders,
  ArrowRight,
  Info,
} from 'lucide-react';
import type { UserRole } from '../components/Sidebar';

interface LoginPageProps {
  onSelectRole: (role: UserRole) => void;
}

interface RoleOption {
  role: UserRole;
  title: string;
  badge: string;
  badgeColor: string;
  icon: React.ElementType;
  iconColor: string;
  iconBg: string;
  description: string;
  destination: string;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onSelectRole }) => {
  const roleOptions: RoleOption[] = [
    {
      role: 'Scrutiny Officer',
      title: 'Scrutiny Officer',
      badge: 'Primary Evaluator',
      badgeColor: 'bg-blue-50 text-blue-700 border-blue-200',
      icon: UserCheck,
      iconColor: 'text-blue-600',
      iconBg: 'bg-blue-100/70',
      description: 'Review prioritized risk queue, inspect evidence-linked findings, and record decisions.',
      destination: 'Opens Triage Queue',
    },
    {
      role: 'Institution',
      title: 'Institution',
      badge: 'Applicant Portal',
      badgeColor: 'bg-amber-50 text-amber-700 border-amber-200',
      icon: Building2,
      iconColor: 'text-amber-600',
      iconBg: 'bg-amber-100/70',
      description: 'Upload documents with an instant quality check',
      destination: 'Opens New Application',
    },
    {
      role: 'Admin',
      title: 'Admin',
      badge: 'System Governance',
      badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      icon: Sliders,
      iconColor: 'text-emerald-600',
      iconBg: 'bg-emerald-100/70',
      description: 'Configure handbook rules and inspect the audit log',
      destination: 'Opens Rules Engine',
    },
  ];

  return (
    <div className="min-h-screen w-screen flex flex-col lg:flex-row bg-slate-900 font-sans selection:bg-blue-500 selection:text-white">
      {/* Left Half: Branding, Overview & Core Pillars */}
      <div className="lg:w-1/2 flex flex-col justify-between p-8 sm:p-12 lg:p-16 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 border-b lg:border-b-0 lg:border-r border-slate-800 text-white relative overflow-hidden">
        {/* Subtle decorative glow */}
        <div className="absolute -top-32 -left-32 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-32 -right-32 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10">
          {/* Logo Section (No official logos / emblems) */}
          <div className="flex items-center gap-3.5 mb-8">
            <div className="w-12 h-12 rounded-xl bg-blue-900 flex items-center justify-center shadow-lg shadow-blue-950/60 border border-blue-700/60 flex-shrink-0 text-white">
              <svg
                className="w-7 h-7"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                {/* Clean Shield + Checkmark */}
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="M9 12l2 2 4-4" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-2xl tracking-tight text-white leading-none">
                  Pramaan<span className="text-blue-400">AI</span>
                </span>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-700/50">
                  Prototype
                </span>
              </div>
              <p className="text-xs text-slate-400 font-medium mt-1">
                Automated Pre-Scrutiny & Evidence Verification Engine
              </p>
            </div>
          </div>

          {/* Tagline / Subtitle */}
          <div className="mb-10 max-w-xl">
            <div className="inline-block px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-slate-300 text-xs font-semibold uppercase tracking-wider mb-3">
              Synthetic Benchmark Dataset
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight leading-snug">
              AI-assisted pre-scrutiny for AICTE approval applications — prototype, synthetic data
            </h1>
            <p className="text-sm text-slate-400 mt-3 leading-relaxed">
              Designed to accelerate statutory compliance checks while keeping scrutiny officers fully in control of every regulatory decision.
            </p>
          </div>

          {/* Three Core Pillars / Small Points with Icons */}
          <div className="space-y-4 max-w-xl">
            <div className="flex items-start gap-3.5 p-3.5 rounded-xl bg-slate-900/80 border border-slate-800/90 shadow-sm backdrop-blur-sm">
              <div className="w-9 h-9 rounded-lg bg-blue-950/90 border border-blue-800/60 text-blue-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                <FileSearch className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-200">
                  Evidence-linked findings
                </h3>
                <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">
                  Every compliance observation and deficit is cited with exact page coordinates and excerpted text snippets.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3.5 p-3.5 rounded-xl bg-slate-900/80 border border-slate-800/90 shadow-sm backdrop-blur-sm">
              <div className="w-9 h-9 rounded-lg bg-emerald-950/90 border border-emerald-800/60 text-emerald-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-200">
                  Source verification
                </h3>
                <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">
                  Automated cross-validation against regulatory registers, building safety clearances, and land records.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3.5 p-3.5 rounded-xl bg-slate-900/80 border border-slate-800/90 shadow-sm backdrop-blur-sm">
              <div className="w-9 h-9 rounded-lg bg-indigo-950/90 border border-indigo-800/60 text-indigo-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                <UserCheck className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-200">
                  Officer decides every outcome
                </h3>
                <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">
                  AI provides non-binding triage assistance; final approval, rejection, or hearing requests remain 100% human-driven.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer info line on left */}
        <div className="mt-8 pt-6 border-t border-slate-800/80 text-xs text-slate-400 flex items-center justify-between">
          <span>AICTE Pre-Scrutiny Workflow Platform</span>
          <span className="font-mono text-[11px] text-slate-400">Release v1.0.0</span>
        </div>
      </div>

      {/* Right Half: Role Selection Card */}
      <div className="lg:w-1/2 flex flex-col justify-center items-center p-6 sm:p-10 lg:p-16 bg-slate-100">
        <div className="w-full max-w-lg">
          {/* Card Container */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl shadow-slate-200/60 p-6 sm:p-8">
            {/* Card Header */}
            <div className="mb-6">
              <span className="text-[11px] font-bold uppercase tracking-wider text-blue-900 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-200 inline-block mb-2">
                Sign In & Role Access
              </span>
              <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                Select Your Role
              </h2>
              <p className="text-xs text-slate-500 mt-1">
                Choose a persona below to explore the application with tailored permissions and workflows.
              </p>
            </div>

            {/* Role Buttons */}
            <div className="space-y-3">
              {roleOptions.map((opt) => {
                const IconComponent = opt.icon;
                return (
                  <button
                    key={opt.role}
                    type="button"
                    onClick={() => onSelectRole(opt.role)}
                    className="w-full text-left p-4 rounded-xl border border-slate-200 hover:border-blue-600 bg-white hover:bg-blue-50/40 transition-all duration-150 group shadow-sm hover:shadow-md cursor-pointer flex items-start gap-4 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  >
                    <div className={`w-10 h-10 rounded-lg ${opt.iconBg} flex items-center justify-center flex-shrink-0 mt-0.5 group-hover:scale-105 transition-transform`}>
                      <IconComponent className={`w-5 h-5 ${opt.iconColor}`} />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="text-sm font-bold text-slate-900 group-hover:text-blue-950">
                          {opt.title}
                        </span>
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${opt.badgeColor}`}>
                          {opt.badge}
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">
                        {opt.description}
                      </p>
                      <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-semibold text-blue-600 group-hover:text-blue-700">
                        <span>{opt.destination}</span>
                        <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Prototype note under the card */}
          <div className="mt-4 px-3 py-2.5 rounded-xl bg-slate-200/60 border border-slate-300/70 text-slate-600 flex items-center gap-2.5 text-xs">
            <Info className="w-4 h-4 text-blue-700 flex-shrink-0" />
            <p className="font-medium leading-relaxed">
              Prototype: role selection stands in for AICTE SSO / JWT login.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
