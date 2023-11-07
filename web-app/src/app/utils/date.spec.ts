import { getTimeLeftForTokenExpiration } from './date';

describe('getTimeLeftForTokenExpiration', () => {
  const nowHours = 12;
  const now = `2023-01-01:${nowHours}:0:0`;

  beforeEach(() => {
    jest.resetAllMocks();
    jest.useFakeTimers().setSystemTime(new Date(now));
  });

  it('returns the duration with all 0s for a now', () => {
    const expectedDuration = {
      years: 0,
      months: 0,
      // weeks: 0,
      days: 0,
      hours: 0,
      minutes: 0,
      seconds: 0,
    };
    const timeLeft = getTimeLeftForTokenExpiration(now);
    expect(timeLeft.duration).toEqual(expectedDuration);
    expect(timeLeft.future).toBe(false);
  });

  it('returns the correct duration for a future date', () => {
    const expectedDuration = {
      years: 0,
      months: 0,
      // weeks: 0,
      days: 0,
      hours: 1,
      minutes: 0,
      seconds: 0,
    };
    const timeLeft = getTimeLeftForTokenExpiration(
      `2023-01-01:${nowHours + 1}:0:0`,
    );
    expect(timeLeft.duration).toEqual(expectedDuration);
    expect(timeLeft.future).toBe(true);
  });

  it('returns the correct duration for a past date', () => {
    const expectedDuration = {
      years: 0,
      months: 0,
      // weeks: 0,
      days: 0,
      hours: 1,
      minutes: 0,
      seconds: 0,
    };
    const timeLeft = getTimeLeftForTokenExpiration(
      `2023-01-01:${nowHours - 1}:0:0`,
    );
    expect(timeLeft.duration).toEqual(expectedDuration);
    expect(timeLeft.future).toBe(false);
  });
});
