import React, { useState, useContext } from 'react';
import type ContextProviderProps from '../interface/ContextProviderProps';

interface AuthContextProps {
  isAuthenticated: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = React.createContext<AuthContextProps | undefined>(
  undefined,
);

export const useAuth = (): AuthContextProps => {
  return useContext(AuthContext) as AuthContextProps;
};

export const AuthProvider: React.FC<ContextProviderProps> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const login = (): void => {
    setIsAuthenticated(true);
  };

  const logout = (): void => {
    setIsAuthenticated(false);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
