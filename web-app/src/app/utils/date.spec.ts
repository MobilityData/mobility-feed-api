import { getTimeLeftForTokenExpiration, displayFormattedDate } from './date';

describe('displayFormattedDate', () => {
  test('returns empty string for null', () => {
    expect(displayFormattedDate(null as unknown as string)).toBe('');
  });

  test('returns empty string for undefined', () => {
    expect(displayFormattedDate(undefined as unknown as string)).toBe('');
  });

  test('returns empty string for empty string', () => {
    expect(displayFormattedDate('')).toBe('');
  });

  test('returns empty string for invalid date string', () => {
    expect(displayFormattedDate('not-a-date')).toBe('');
  });

  test('returns formatted string for valid ISO date', () => {
    const result = displayFormattedDate('2023-01-01T12:00:00Z');
    // Format manually to match expected UTC time
    expect(result).toBe(
      new Intl.DateTimeFormat('en-US', {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'UTC',
      }).format(new Date('2023-01-01T12:00:00Z')),
    );
  });

  test('returns formatted string for valid date-only string', () => {
    const result = displayFormattedDate('2023-01-01');
    expect(result).toBe(
      new Intl.DateTimeFormat('en-US', {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'UTC',
      }).format(new Date('2023-01-01')),
    );
  });

  test('returns formatted string for ISO with timezone offset', () => {
    const result = displayFormattedDate('2023-01-01T12:00:00-05:00');
    expect(result).toBe(
      new Intl.DateTimeFormat('en-US', {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'UTC',
      }).format(new Date('2023-01-01T12:00:00-05:00')),
    );
  });
});

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
