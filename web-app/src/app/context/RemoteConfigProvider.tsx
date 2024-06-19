import React, {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from 'react';
import { remoteConfig } from '../../firebase';
import {
  defaultRemoteConfigValues,
  type RemoteConfigValues,
} from '../interface/RemoteConfig';
import i18n from '../../i18n';

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
            // Boolean
            fetchedConfigValues[key] = rawValue.asBoolean();
          } else if (!isNaN(Number(rawValue)) && rawValueLower.trim() !== '') {
            // Number
            fetchedConfigValues[key] = rawValue.asNumber();
          } else {
            // Default to string
            fetchedConfigValues[key] = rawValue.asString();
          }
        });

        const newConfig = {
          ...config,
          ...fetchedConfigValues,
        };

        setConfig(newConfig);

        if (!newConfig.enableLanguageToggle) {
          void i18n.changeLanguage('en');
        }
      } catch (error) {
        // pass -- default values will be used
      } finally {
        setLoading(false);
      }
    };

    void fetchAndActivateConfig();
  }, []);

  return (
    <RemoteConfigContext.Provider value={{ config, loading }}>
      {children}
    </RemoteConfigContext.Provider>
  );
};

export const useRemoteConfig = (): {
  config: RemoteConfigValues;
} => useContext(RemoteConfigContext);
