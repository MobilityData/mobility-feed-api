'use client';

import * as React from 'react';
import ContextProviders from './components/Context';
import { RemoteConfigProvider } from './context/RemoteConfigProvider';

// Look into this provider and see if it's client blocking. Niche provider might be able to isolate for single use
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';

import AuthTokenSync from './components/AuthTokenSync';

/// FOR SSR all these providers will need to be refactored
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ContextProviders>
      <AuthTokenSync />
      <RemoteConfigProvider>
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          {children}
        </LocalizationProvider>
      </RemoteConfigProvider>
    </ContextProviders>
  );
}
