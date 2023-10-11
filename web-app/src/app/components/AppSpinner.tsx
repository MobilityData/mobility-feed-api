import * as React from 'react';
import type ContextProviderProps from '../interface/ContextProviderProps';
import LoadingOverlay from 'react-loading-overlay-ts';
import { useSelector } from 'react-redux';
import { selectLoadingApp } from '../store/selectors';

const AppSpinner: React.FC<ContextProviderProps> = ({ children }) => {
  const isActive = useSelector(selectLoadingApp);
  return (
    <LoadingOverlay active={isActive} spinner>
      {children}
    </LoadingOverlay>
  );
};

export default AppSpinner;
