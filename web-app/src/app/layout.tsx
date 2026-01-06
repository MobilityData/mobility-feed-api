import * as React from 'react';
import ThemeRegistry from './registry';

import { Providers } from './providers';

export const metadata = {
  title: 'Mobility Database',
  description: 'Mobility Database',
};

import { Mulish, IBM_Plex_Mono } from 'next/font/google';
import Footer from './components/Footer';
import Header from './components/Header';

const mulish = Mulish({
  weight: ['400', '700'],
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-mulish',
});

const ibmPlexMono = IBM_Plex_Mono({
  weight: ['400', '700'],
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-ibm-plex-mono',
});

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang='en'>
      <body className={`${mulish.variable} ${ibmPlexMono.variable}`}>
        <ThemeRegistry>
          <Providers>
            <Header />
            <main id='next'>{children}</main>
            <Footer />
          </Providers>
        </ThemeRegistry>
      </body>
    </html>
  );
}
