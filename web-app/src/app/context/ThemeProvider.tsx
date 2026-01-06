'use client';

import { createContext, useState, useMemo, useContext } from 'react';
import {
  ThemeProvider as MuiThemeProvider,
  CssBaseline,
  useMediaQuery,
} from '@mui/material';
import { getTheme, ThemeModeEnum } from '../Theme';
import type ContextProviderProps from '../interface/ContextProviderProps';

const ThemeContext = createContext({ toggleTheme: () => {} });

function getInitialThemeMode(prefersDarkMode: boolean): ThemeModeEnum {
  if (typeof window !== 'undefined' && localStorage.getItem('theme') != null) {
    return localStorage.getItem('theme') as ThemeModeEnum;
  } else {
    return prefersDarkMode ? ThemeModeEnum.dark : ThemeModeEnum.light;
  }
}

export const ThemeProvider: React.FC<ContextProviderProps> = ({ children }) => {
  const prefersDarkMode = useMediaQuery('(prefers-color-scheme: dark)');
  const [mode, setMode] = useState<ThemeModeEnum>(
    getInitialThemeMode(prefersDarkMode),
  );

  const toggleTheme = (): void => {
    const newMode =
      mode === ThemeModeEnum.light ? ThemeModeEnum.dark : ThemeModeEnum.light;
    setMode(newMode);
    localStorage.setItem('theme', newMode);
  };

  const theme = useMemo(() => getTheme(mode), [mode]);

  return (
    <ThemeContext.Provider value={{ toggleTheme }}>
      <MuiThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ThemeContext.Provider>
  );
};

export const useTheme = (): { toggleTheme: () => void } =>
  useContext(ThemeContext);
