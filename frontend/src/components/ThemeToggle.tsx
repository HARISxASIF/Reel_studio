'use client';

import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '@/context/ThemeContext';

interface ThemeToggleProps {
  className?: string;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({ className = '' }) => {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';
  const label = isDark ? 'Switch to light theme' : 'Switch to dark theme';

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={label}
      title={label}
      className={`relative inline-flex h-9 w-9 items-center justify-center rounded-xl border border-divider bg-surface-raised text-text-primary hover:bg-surface hover:text-accent focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-2 focus:ring-offset-page transition-all duration-200 cursor-pointer ${className}`}
    >
      <span className="sr-only">{label}</span>
      {isDark ? (
        <Sun className="h-4 w-4 text-amber-400 transition-transform duration-300 hover:rotate-45" />
      ) : (
        <Moon className="h-4 w-4 text-violet-600 transition-transform duration-300 hover:-rotate-12" />
      )}
    </button>
  );
};
