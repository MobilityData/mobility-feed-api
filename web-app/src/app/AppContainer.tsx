import * as React from 'react';
import { useSelector } from 'react-redux';
import { Box, LinearProgress } from '@mui/material';
import { selectLoadingApp } from './store/selectors';
import type ContextProviderProps from './interface/ContextProviderProps';
import Footer from './components/Footer';
import Header from './components/Header';
import { useLocation } from 'react-router-dom';

const AppContainer: React.FC<ContextProviderProps> = ({ children }) => {
  const isAppLoading = useSelector(selectLoadingApp);
  const location = useLocation();

  React.useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [location.pathname]);

  return (
    <Box id='app-main-container'>
      <Header />
      {isAppLoading ? (
        <Box sx={{ width: '100%', mt: '-31px' }}>
          <LinearProgress />
        </Box>
      ) : (
        children
      )}
      <Footer />
    </Box>
  );
};

export default AppContainer;
