import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './app/App';
import ReactGA from 'react-ga4';
import { getEnvConfig } from './app/utils/config';
import ContextProviders from './app/components/Context';
import { CssBaseline } from '@mui/material';
import { ThemeProvider } from './app/context/ThemeProvider';

const gaId = getEnvConfig('REACT_APP_GOOGLE_ANALYTICS_ID');
if (gaId.length > 0) {
  ReactGA.initialize(gaId);
  ReactGA.send('pageview');
}

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement,
);
root.render(
  <React.StrictMode>
    <ThemeProvider>
      <CssBaseline />
      <ContextProviders>
        <App />
      </ContextProviders>
    </ThemeProvider>
  </React.StrictMode>
);
