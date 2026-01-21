import * as React from 'react';
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';
import { ThemeProvider } from './context/ThemeProvider';

export default function ThemeRegistry({
  children,
}: {
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <AppRouterCacheProvider options={{ key: 'mui' }}>
      <ThemeProvider>{children}</ThemeProvider>
    </AppRouterCacheProvider>
  );
}
