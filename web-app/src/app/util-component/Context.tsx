import React from 'react';
import { AuthProvider } from '../sign-in-page/AuthContext';
import type ContextProviderProps from '../interface/ContextProviderProps';

const ContextProviders: React.FC<ContextProviderProps> = ({ children }) => {
  return (
    <AuthProvider>
      {/* Add other providers here */}
      {children}
    </AuthProvider>
  );
};

export default ContextProviders;
