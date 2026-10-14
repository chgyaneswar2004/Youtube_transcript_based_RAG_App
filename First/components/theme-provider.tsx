'use client';

import { useEffect } from 'react';

interface ThemeProviderProps {
  children: React.ReactNode;
  attribute: string;
  defaultTheme: string;
  enableSystem: boolean;
}

export function ThemeProvider({
  children,
  attribute,
  defaultTheme,
  enableSystem,
}: ThemeProviderProps) {
  useEffect(() => {
    // Load saved theme or default
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = savedTheme || (enableSystem && prefersDark ? 'dark' : defaultTheme);
    
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [defaultTheme, enableSystem]);

  return <>{children}</>;
}
