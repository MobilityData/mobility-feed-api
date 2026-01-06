/**
 * Get environment config.
 * If the value is a placeholder means the value was not set properly, return an empty string
 * @param key variable key
 * @returns variable value or empty string
 */
export const getEnvConfig = (key: string): string => {
  const value = process.env[key] ?? '';
  return value === '{{' + key + '}}' ? '' : value.trim();
};

export const getProjectShortName = (): 'dev' | 'qa' | 'prod' => {
  // Example value: mobility-feeds-dev
  let result: 'dev' | 'qa' | 'prod' = 'prod';
  const projectId = getEnvConfig('NEXT_PUBLIC_FIREBASE_PROJECT_ID');
  if (projectId.length > 0) {
    const nameSections = projectId.split('-');
    if (nameSections.length == 3) {
      const rawShortName = nameSections[2].toLowerCase();
      switch (rawShortName) {
        case 'dev':
        case 'qa':
          result = rawShortName;
          break;
      }
    }
  }
  return result;
};

export const getFeedFilesBaseUrl = (): string => {
  const projectShortName = getProjectShortName();
  let prefix = '';
  switch (projectShortName) {
    case 'dev':
    case 'qa':
      prefix = `${projectShortName}-`;
  }
  return `https://${prefix}files.mobilitydatabase.org`;
};
