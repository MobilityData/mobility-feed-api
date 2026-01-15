'use client';

import React, { createContext, type ReactNode, useContext } from 'react';
import {
  defaultRemoteConfigValues,
  type RemoteConfigValues,
} from '../interface/RemoteConfig';

const RemoteConfigContext = createContext<{
  config: RemoteConfigValues;
}>({
  config: defaultRemoteConfigValues,
});

interface RemoteConfigProviderProps {
  children: ReactNode;
  config: RemoteConfigValues;
}

/**
 * Client-side Remote Config provider that hydrates server-fetched config into React Context.
 * This provider does NOT fetch config - it receives pre-fetched values from the server.
 */
export const RemoteConfigProvider = ({
  children,
  config,
}: RemoteConfigProviderProps): React.ReactElement => {
  return (
    <RemoteConfigContext.Provider value={{ config }}>
      {children}
    </RemoteConfigContext.Provider>
  );
};

/**
 * Hook to access Remote Config values from any client component.
 */
export const useRemoteConfig = (): {
  config: RemoteConfigValues;
} => useContext(RemoteConfigContext);
