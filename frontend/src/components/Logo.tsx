import React from 'react';

interface LogoProps {
  collapsed?: boolean;
}

export const Logo: React.FC<LogoProps> = ({ collapsed = false }) => {
  return (
    <div className="flex items-center gap-3">
      {/* Original Shield + Checkmark SVG */}
      <div className="w-10 h-10 rounded-lg bg-blue-900 flex items-center justify-center shadow-md flex-shrink-0 text-white">
        <svg
          className="w-6 h-6"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {/* Shield */}
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          {/* Check mark */}
          <path d="M9 12l2 2 4-4" />
        </svg>
      </div>

      {!collapsed && (
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-lg tracking-tight text-white leading-none">
              Pramaan<span className="text-blue-400">AI</span>
            </span>
            <span className="text-[10px] uppercase font-semibold tracking-wider px-1.5 py-0.5 rounded bg-blue-900/60 text-blue-300 border border-blue-700/50">
              Prototype
            </span>
          </div>
          <span className="text-[11px] text-slate-400 font-medium leading-tight mt-1 line-clamp-1">
            AI-assisted application validation — SIH 2026 PS 26261 prototype
          </span>
        </div>
      )}
    </div>
  );
};
