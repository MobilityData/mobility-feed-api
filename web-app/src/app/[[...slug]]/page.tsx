'use client';

// This page is temporary to ease the migration to Next.js App Router
// It will be deprecated once the migration is fully complete
import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';

const App = dynamic(async () => await import('../App'), { ssr: false });

export default function Page(): JSX.Element | null {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return null;
  }

  return <App />;
}
