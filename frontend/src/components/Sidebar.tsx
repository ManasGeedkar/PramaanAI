import React from 'react';
import { Logo } from './Logo';
import {
  Inbox,
  BarChart3,
  FileCheck2,
  Sliders,
  History,
  UserCheck,
  Building2,
  Shield,
  Layers,
  FileUp,
} from 'lucide-react';

export type UserRole = 'Scrutiny Officer' | 'Institution' | 'Admin';

interface SidebarProps {
  currentTab: string;
  onTabChange: (tab: string) => void;
  role: UserRole;
  onRoleChange: (role: UserRole) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  role,
  onRoleChange,
}) => {
  const navItems = [
    {
      id: 'queue',
      label: 'Triage Queue',
      icon: Inbox,
      roles: ['Scrutiny Officer', 'Admin'],
      badge: 'Live',
    },
    {
      id: 'upload',
      label: 'New Application',
      icon: FileUp,
      roles: ['Institution', 'Admin', 'Scrutiny Officer'],
    },
    {
      id: 'overview',
      label: 'Management Overview',
      icon: BarChart3,
      roles: ['Scrutiny Officer', 'Admin', 'Institution'],
    },
    {
      id: 'evaluate',
      label: 'Benchmark Evaluation',
      icon: FileCheck2,
      roles: ['Scrutiny Officer', 'Admin'],
    },
    {
      id: 'audit',
      label: 'Audit Log & Chain',
      icon: History,
      roles: ['Scrutiny Officer', 'Admin'],
    },
    {
      id: 'rules',
      label: 'Rules Engine (Admin)',
      icon: Sliders,
      roles: ['Admin'],
    },
  ];

  const visibleNavItems = navItems.filter((item) => item.roles.includes(role));

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col border-r border-slate-800 flex-shrink-0">
      {/* Top Branding */}
      <div className="p-4 border-b border-slate-800 bg-slate-950">
        <Logo />
      </div>

      {/* Role Switcher */}
      <div className="p-3 border-b border-slate-800 bg-slate-900/60">
        <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5 flex items-center justify-between">
          <span>Active Role</span>
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
        </label>
        <div className="relative">
          <select
            value={role}
            onChange={(e) => onRoleChange(e.target.value as UserRole)}
            className="w-full bg-slate-800 border border-slate-700 text-white rounded-md px-3 py-1.5 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer appearance-none pr-8"
          >
            <option value="Scrutiny Officer">Scrutiny Officer</option>
            <option value="Institution">Institution Representative</option>
            <option value="Admin">System Administrator</option>
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-slate-400">
            <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 20 20">
              <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" />
            </svg>
          </div>
        </div>

        {/* Role Helper Text */}
        <div className="mt-2 text-[10px] text-slate-400 flex items-center gap-1.5 px-0.5">
          {role === 'Scrutiny Officer' && (
            <>
              <UserCheck className="w-3 h-3 text-blue-400" />
              <span>Prioritised risk queue & audit scrutiny</span>
            </>
          )}
          {role === 'Institution' && (
            <>
              <Building2 className="w-3 h-3 text-amber-400" />
              <span>Submission tracking & guidance</span>
            </>
          )}
          {role === 'Admin' && (
            <>
              <Shield className="w-3 h-3 text-emerald-400" />
              <span>Rules configuration & pipeline logs</span>
            </>
          )}
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        <div className="text-[10px] uppercase font-bold tracking-wider text-slate-400 px-3 py-1.5">
          Portal Navigation
        </div>
        {visibleNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-blue-800 text-white shadow-sm shadow-blue-950 font-semibold'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span className="text-[9px] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* System Status Pill */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/70 text-[11px] text-slate-400 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-blue-400" />
          <span>Pipeline: <strong className="text-slate-200">8 Stages Active</strong></span>
        </div>
        <span className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-slate-800 text-slate-300">
          v1.0.0
        </span>
      </div>
    </aside>
  );
};
