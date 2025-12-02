import React, { createContext, useContext, useMemo, useState } from 'react';
import {
  type BasicAuth,
  type BearerTokenAuth,
  type OAuthClientCredentialsGrantAuth,
} from '../store/gbfs-validator-reducer';

export enum AuthTypeEnum {
  BASIC = 'BasicAuth',
  BEARER = 'BearerTokenAuth',
  OAUTH = 'OAuthClientCredentialsGrantAuth',
}

export type GbfsAuthDetails =
  | BasicAuth
  | BearerTokenAuth
  | OAuthClientCredentialsGrantAuth
  | undefined;

interface GbfsAuthContextValue {
  auth: GbfsAuthDetails;
  setAuth: (details: GbfsAuthDetails) => void;
  clearAuth: () => void;
  buildAuthHeaders: () => Promise<Record<string, string> | undefined>;
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

  const buildAuthHeaders = async (): Promise<
    Record<string, string> | undefined
  > => {
    if (
      auth?.authType === AuthTypeEnum.BASIC &&
      'username' in auth &&
      'password' in auth &&
      auth.username != null &&
      auth.username.trim() !== '' &&
      auth.password != null &&
      auth.password.trim() !== ''
    ) {
      try {
        const token = btoa(`${auth.username}:${auth.password}`);
        return { Authorization: `Basic ${token}` };
      } catch {
        return undefined;
      }
    }
    if (
      auth?.authType === AuthTypeEnum.BEARER &&
      'token' in auth &&
      auth.token != null &&
      auth.token.trim() !== ''
    ) {
      return { Authorization: `Bearer ${auth.token}` };
    }
    if (
      auth?.authType === AuthTypeEnum.OAUTH &&
      'clientId' in auth &&
      'clientSecret' in auth &&
      'tokenUrl' in auth &&
      auth.clientId != null &&
      auth.clientId.trim() !== '' &&
      auth.clientSecret != null &&
      auth.clientSecret.trim() !== '' &&
      auth.tokenUrl != null &&
      auth.tokenUrl.trim() !== ''
    ) {
      const tokenResp = await fetch(auth.tokenUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          Authorization: `Basic ${btoa(
            `${auth.clientId}:${auth.clientSecret}`,
          )}`,
        },
        body: 'grant_type=client_credentials',
        credentials: 'omit',
      });
      if (!tokenResp.ok) {
        return undefined;
      }
      const tokenJson = await tokenResp.json();
      const accessToken = tokenJson?.access_token ?? tokenJson?.token;
      if (accessToken == null) {
        return undefined;
      }
      const tokenType = tokenJson?.token_type ?? 'Bearer';
      return { Authorization: `${tokenType} ${accessToken}` };
    }
    return undefined;
  };

  const value = useMemo(
    () => ({ auth, setAuth, clearAuth, buildAuthHeaders }),
    [auth, setAuth, clearAuth, buildAuthHeaders],
  );

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
