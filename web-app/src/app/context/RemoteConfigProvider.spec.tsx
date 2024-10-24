import { type BypassConfig } from '../interface/RemoteConfig';
import { userHasBypass } from './RemoteConfigProvider';
jest.mock('firebase/compat/app', () => ({
  initializeApp: jest.fn(),
  remoteConfig: jest.fn(() => ({
    settings: { minimumFetchIntervalMillis: 3600000 },
  })),
}));
describe('userHasBypass', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should return false if userEmail is null', () => {
    const byPassConfig: BypassConfig = { regex: ['.*@example.com'] };
    expect(userHasBypass(byPassConfig, null)).toBe(false);
  });

  it('should return false if userEmail is undefined', () => {
    const byPassConfig: BypassConfig = { regex: ['.*@example.com'] };
    expect(userHasBypass(byPassConfig, undefined)).toBe(false);
  });

  it('should return true if userEmail matches one of the regex patterns', () => {
    const byPassConfig: BypassConfig = { regex: ['.*@example.com'] };
    expect(userHasBypass(byPassConfig, 'test@example.com')).toBe(true);
  });

  it('should return false if userEmail does not match any regex patterns', () => {
    const byPassConfig: BypassConfig = { regex: ['.*@example.com'] };
    expect(userHasBypass(byPassConfig, 'test@otherdomain.com')).toBe(false);
  });

  it('should return true if userEmail matches multiple regex patterns', () => {
    const byPassConfig: BypassConfig = {
      regex: ['.*@example.com', '.*@another.com'],
    };
    expect(userHasBypass(byPassConfig, 'test@another.com')).toBe(true);
  });

  it('should return false if byPassConfig has an empty regex array', () => {
    const byPassConfig: BypassConfig = { regex: [] };
    expect(userHasBypass(byPassConfig, 'test@example.com')).toBe(false);
  });

  it('should return true if user is in list of regex', () => {
    const byPassConfig: BypassConfig = {
      regex: ['alex@example.com', 'bill@example.com'],
    };
    expect(userHasBypass(byPassConfig, 'bIll@example.com')).toBe(true);
  });

  it('should return false if user is not in list', () => {
    const byPassConfig: BypassConfig = {
      regex: ['alex@example.com', 'bill@example.com'],
    };
    expect(userHasBypass(byPassConfig, 'cris@example.com')).toBe(false);
  });

  it('should not break the function if there is an invalid regex', () => {
    const byPassConfig: BypassConfig = {
      regex: ['alex@example.org(', 'bill@example.com'],
    };
    expect(userHasBypass(byPassConfig, 'bill@example.com')).toBe(true);
  });
});
