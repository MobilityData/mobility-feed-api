import { getEnvConfig } from './config';

describe('getEnvConfig', () => {
  describe('valid env variable', () => {
    const originalEnv = process.env;
    beforeEach(() => {
      jest.resetModules();
      process.env = {
        ...originalEnv,
        REACT_APP_GOOGLE_ANALYTICS_ID: '  This is the value  ',
      };
    });

    it('should return the environment variable value if it is set and trimmed', () => {
      expect(getEnvConfig('REACT_APP_GOOGLE_ANALYTICS_ID')).toEqual(
        'This is the value',
      );
    });
  });

  describe('placeholder env variable', () => {
    const originalEnv = process.env;
    beforeEach(() => {
      jest.resetModules();
      process.env = {
        ...originalEnv,
        REACT_APP_GOOGLE_ANALYTICS_ID: '{{REACT_APP_GOOGLE_ANALYTICS_ID}}',
      };
    });

    it('should return an empty string if the value is a placeholder', () => {
      expect(getEnvConfig('REACT_APP_GOOGLE_ANALYTICS_ID')).toEqual('');
    });
  });
});
