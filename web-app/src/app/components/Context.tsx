'use client';

import React, { useEffect } from 'react';
import type ContextProviderProps from '../interface/ContextProviderProps';
import { Provider } from 'react-redux';
import { store } from '../store/store';
import { PersistGate } from 'redux-persist/integration/react';
import { persistStore } from 'redux-persist';
import { useAppDispatch } from '../hooks';
import { resetProfileErrors } from '../store/profile-reducer';

const persistor = persistStore(store);
/**
 * This component is used to wrap the entire application
 */
const AppContent: React.FC<ContextProviderProps> = ({ children }) => {
  const dispatch = useAppDispatch();

  useEffect(() => {
    // This function will run when the component is first loaded
    // Clean errros from previous session
    dispatch(resetProfileErrors());
  }, []);
  return (
    <PersistGate loading={null} persistor={persistor}>
      {children}
    </PersistGate>
  );
};

/**
 * This component is used to wrap the entire application adding the store provider and reseting the errors from previous session
 */
const ContextProviders: React.FC<ContextProviderProps> = ({ children }) => {
  return (
    <Provider store={store}>
      <AppContent>{children}</AppContent>
    </Provider>
  );
};

export default ContextProviders;
