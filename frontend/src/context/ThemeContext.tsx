'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';

type Theme = 'dark' | 'light';

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<Theme>('dark');
  const [mounted, setMounted] = useState(false);

  // Apply theme to document element
  const applyTheme = useCallback((newTheme: Theme) => {
    const root = document.documentElement;
    root.classList.remove('dark', 'light');
    root.classList.add(newTheme);
    root.setAttribute('data-theme', newTheme);
    root.style.colorScheme = newTheme;
  }, []);

  useEffect(() => {
    setMounted(true);
    // 1. Check localStorage first
    const saved = localStorage.getItem('reelstudio_theme') as Theme | null;
    if (saved === 'dark' || saved === 'light') {
      setThemeState(saved);
      applyTheme(saved);
      return;
    }

    // 2. Follow device preference
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initialTheme: Theme = prefersDark ? 'dark' : 'light';
    setThemeState(initialTheme);
    applyTheme(initialTheme);

    // 3. Listen for system theme changes if user hasn't explicitly set preference
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e: MediaQueryListEvent) => {
      const userSaved = localStorage.getItem('reelstudio_theme');
      if (!userSaved) {
        const sysTheme: Theme = e.matches ? 'dark' : 'light';
        setThemeState(sysTheme);
        applyTheme(sysTheme);
      }
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [applyTheme]);

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
    localStorage.setItem('reelstudio_theme', newTheme);
    applyTheme(newTheme);
  };

  const toggleTheme = () => {
    const nextTheme: Theme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};
