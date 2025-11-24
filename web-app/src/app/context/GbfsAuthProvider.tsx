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
      auth.password != null
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
      auth.token != null
    ) {
      return { Authorization: `Bearer ${auth.token}` };
    }
    if (
      auth?.authType === AuthTypeEnum.OAUTH &&
      'clientId' in auth &&
      'clientSecret' in auth &&
      'tokenUrl' in auth &&
      auth.clientId != null &&
      auth.clientSecret != null &&
      auth.tokenUrl != null
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
        throw new Error(
          `OAuth token request failed (HTTP ${tokenResp.status})`,
        );
      }
      const tokenJson = await tokenResp.json();
      const accessToken = tokenJson?.access_token ?? tokenJson?.token;
      if (accessToken == null) {
        throw new Error('OAuth token response missing access_token');
      }
      const tokenType = tokenJson?.token_type ?? 'Bearer';
      return { Authorization: `${tokenType} ${accessToken}` };
    }
    return undefined;
  };

  const value = useMemo(
    () => ({ auth, setAuth, clearAuth, buildAuthHeaders }),
    [auth],
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
