import React, { createContext, useContext, useMemo, useState } from 'react';
import { type components } from '../services/feeds/gbfs-validator-types';

export enum AuthTypeEnum {
  BASIC = 'BasicAuth',
  BEARER = 'BearerTokenAuth',
  OAUTH = 'OAuthClientCredentialsGrantAuth',
}

export type GbfsAuthDetails =
  | components['schemas']['BasicAuth']
  | components['schemas']['BearerTokenAuth']
  | components['schemas']['OAuthClientCredentialsGrantAuth']
  | undefined;

interface GbfsAuthContextValue {
  auth: GbfsAuthDetails;
  setAuth: (details: GbfsAuthDetails) => void;
  clearAuth: () => void;
}

const GbfsAuthContext = createContext<GbfsAuthContextValue | undefined>(
  undefined,
);

const defaultAuth: GbfsAuthDetails = undefined;

export function GbfsAuthProvider({
  children,
}: {
  children: React.ReactNode;
}): React.ReactElement {
  const [auth, setAuthState] = useState<GbfsAuthDetails>(defaultAuth);

  const setAuth = (details: GbfsAuthDetails): void => {
    setAuthState(details);
  };

  const clearAuth = (): void => {
    setAuthState(defaultAuth);
  };

  const value = useMemo(() => ({ auth, setAuth, clearAuth }), [auth]);

  return (
    <GbfsAuthContext.Provider value={value}>
      {children}
    </GbfsAuthContext.Provider>
  );
}

export function useGbfsAuth(): GbfsAuthContextValue {
  const ctx = useContext(GbfsAuthContext);
  if (ctx == null) {
    throw new Error('useGbfsAuth must be used within GbfsAuthProvider');
  }
  return ctx;
}
