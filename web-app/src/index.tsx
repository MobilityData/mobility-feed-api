import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './app/App';
import { theme } from './app/Theme';
import { ThemeProvider } from '@mui/material/styles';
import ReactGA from 'react-ga4';
import { getEnvConfig } from './app/utils/config';

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
    <ThemeProvider theme={theme}>
      <App />
    </ThemeProvider>
  </React.StrictMode>,
);
