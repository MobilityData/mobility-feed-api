import React from 'react';
import type ContextProviderProps from '../interface/ContextProviderProps';
import { Provider } from 'react-redux';
import { store } from '../store/store';
import { PersistGate } from 'redux-persist/integration/react';
import { persistStore } from 'redux-persist';

const persistor = persistStore(store);

const ContextProviders: React.FC<ContextProviderProps> = ({ children }) => {
  return (
    <Provider store={store}>
      <PersistGate loading={null} persistor={persistor}>
        {children}
      </PersistGate>
    </Provider>
  );
};

export default ContextProviders;
