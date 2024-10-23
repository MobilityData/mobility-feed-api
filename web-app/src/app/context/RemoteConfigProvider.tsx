import React, {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from 'react';
import { remoteConfig, app } from '../../firebase';
import {
  ByPassConfig,
  defaultRemoteConfigValues,
  type RemoteConfigValues,
} from '../interface/RemoteConfig';

const RemoteConfigContext = createContext<{
  config: RemoteConfigValues;
  loading: boolean;
}>({
  config: defaultRemoteConfigValues,
  loading: true,
});

interface RemoteConfigProviderProps {
  children: ReactNode;
}

export function doesUserHaveBypass(byPassConfig: ByPassConfig, userEmail: string | null | undefined) {
  let hasBypass = false;
  if(userEmail === null || userEmail === undefined) {
    return false;
  }
  byPassConfig.regex.forEach((regex) => {
    try {
      if(userEmail.match(new RegExp(regex, 'i')) !== null) {
        hasBypass = true;
      }
    } catch (e) {
      console.error(`Invalid regex: ${regex}`);
    }
  });
  return hasBypass;
}

export const RemoteConfigProvider = ({
  children,
}: RemoteConfigProviderProps): React.ReactElement => {
  const [config, setConfig] = useState<RemoteConfigValues>(
    defaultRemoteConfigValues,
  );
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchAndActivateConfig = async (): Promise<void> => {
      try {
        await remoteConfig.fetchAndActivate();
        const fetchedConfigValues = defaultRemoteConfigValues;
        Object.keys(defaultRemoteConfigValues).forEach((key) => {
          const rawValue = remoteConfig.getValue(key);
          const rawValueLower = rawValue.asString().toLowerCase();
          if (rawValueLower === 'true' || rawValueLower === 'false') {
            const bypassConfig: ByPassConfig = JSON.parse(remoteConfig.getValue('featureFlagBypass').asString());
            const hasBypass = doesUserHaveBypass(bypassConfig, app.auth().currentUser?.email)
            fetchedConfigValues[key] = hasBypass ? hasBypass : rawValue.asBoolean();
          } else if (!isNaN(Number(rawValue)) && rawValueLower.trim() !== '') {
            // Number
            fetchedConfigValues[key] = rawValue.asNumber();
          } else {
            // Default to string
            fetchedConfigValues[key] = rawValue.asString();
          }
        });
        setConfig((prevConfig) => ({
          ...prevConfig,
          ...fetchedConfigValues,
        }));
      } catch (error) {
        // pass -- default values will be used
      } finally {
        setLoading(false);
      }
    };

    void fetchAndActivateConfig();
  }, [app.auth().currentUser?.email]);

  return (
    <RemoteConfigContext.Provider value={{ config, loading }}>
      {children}
    </RemoteConfigContext.Provider>
  );
};

export const useRemoteConfig = (): {
  config: RemoteConfigValues;
} => useContext(RemoteConfigContext);
