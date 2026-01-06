'use client';

import * as React from 'react';
import NextAppDirEmotionCacheProvider from './emotion-cache';
import { ThemeProvider } from './context/ThemeProvider';

export default function ThemeRegistry({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <NextAppDirEmotionCacheProvider options={{ key: 'mui' }}>
      <ThemeProvider>{children}</ThemeProvider>
    </NextAppDirEmotionCacheProvider>
  );
}
