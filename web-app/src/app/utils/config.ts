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
