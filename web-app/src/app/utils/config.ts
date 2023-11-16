/**
 * Get environment config
 * @param key variable key
 * @returns variable value or empty string
 */
export const getEnvConfig = (key: string): string => {
  return process.env[key] ?? '';
};
