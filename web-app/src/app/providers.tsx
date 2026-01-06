'use client';

import * as React from 'react';
import ContextProviders from './components/Context';
import { RemoteConfigProvider } from './context/RemoteConfigProvider';
import { I18nextProvider } from 'react-i18next';
import i18n from '../i18n';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import AuthTokenSync from './components/AuthTokenSync';

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ContextProviders>
      <AuthTokenSync />
      <RemoteConfigProvider>
        <I18nextProvider i18n={i18n}>
          <LocalizationProvider dateAdapter={AdapterDayjs}>
            {children}
          </LocalizationProvider>
        </I18nextProvider>
      </RemoteConfigProvider>
    </ContextProviders>
  );
}
