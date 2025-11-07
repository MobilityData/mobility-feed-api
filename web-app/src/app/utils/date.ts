import { utcToZonedTime } from 'date-fns-tz';
import { intervalToDuration, isFuture } from 'date-fns';

export const displayFormattedDate = (stringDate?: string): string => {
  if (stringDate == null) {
    return '';
  }
  const date = new Date(stringDate);
  // Check if the date is valid
  if (isNaN(date.getTime())) {
    return '';
  }
  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'UTC',
  }).format(date);
};

export const formatDateShort = (
  dateString: string,
  timeZone?: string,
): string => {
  const usedTimezone = timeZone ?? 'UTC';
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-US', {
    timeZone: usedTimezone,
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
};

/**
 *
 * @param dateString date in ISO format
 * @returns Duration object with the time left for the token to expire
 */
export const getTimeLeftForTokenExpiration = (
  dateString: string,
): { future: boolean; duration: Duration } => {
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const targetDate = utcToZonedTime(new Date(dateString), timeZone);
  const now = utcToZonedTime(new Date(), timeZone);

  return {
    future: isFuture(targetDate),
    duration: intervalToDuration({ start: now, end: targetDate }),
  };
};

/**
 *
 * @param duration Duration object
 * @returns the formatted string of the duration wiht the pattern HH:MM:SS
 */
export const formatTokenExpiration = (duration: Duration): string => {
  const hours = ((duration?.days ?? 0) * 24 + (duration?.hours ?? 0))
    .toString()
    .padStart(2, '0');
  const minutes = (duration?.minutes ?? 0).toString().padStart(2, '0');
  const seconds = (duration?.seconds ?? 0).toString().padStart(2, '0');

  return `${hours}:${minutes}:${seconds}`;
};
