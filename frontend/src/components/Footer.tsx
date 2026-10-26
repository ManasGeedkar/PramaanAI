import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="mt-auto border-t border-slate-200 bg-white py-3 px-6 text-center">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-2">
        <p className="font-medium text-slate-600">
          AI findings are advisory. Final decisions rest with competent AICTE authorities.
        </p>
        <p className="text-slate-400">
          PramaanAI Prototype • SIH 2026 Problem Statement 26261
        </p>
      </div>
    </footer>
  );
};
