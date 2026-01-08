import * as React from 'react';
import { useSelector } from 'react-redux';
import { Box, LinearProgress } from '@mui/material';
import { selectLoadingApp } from './store/selectors';
import type ContextProviderProps from './interface/ContextProviderProps';
import Footer from './components/Footer';
import Header from './components/Header';
import { useLocation } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';

const AppContainer: React.FC<ContextProviderProps> = ({ children }) => {
  const isAppLoading = false;//useSelector(selectLoadingApp);
  const location = useLocation();
  const canonicalUrl = window.location.origin + location.pathname;

  React.useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [location.pathname]);

  return (
    <>
      <Helmet>
        <link rel='canonical' href={canonicalUrl} />
      </Helmet>
      <Box id='app-main-container'>
        {isAppLoading ? (
          <Box sx={{ width: '100%', mt: '-31px' }}>
            <LinearProgress />
          </Box>
        ) : (
          <>
            {children}
          </>
        )}
      </Box>
    </>
  );
};

export default AppContainer;
