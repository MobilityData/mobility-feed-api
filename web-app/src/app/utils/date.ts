import { utcToZonedTime } from 'date-fns-tz';
import { intervalToDuration } from 'date-fns';

export function getTimeLeftForTokenExpiration(
  timeZone: string,
  dateString?: string,
): string {
  if (dateString === undefined) return 'No date provided';
  const targetDate = utcToZonedTime(new Date(dateString), timeZone);
  const now = utcToZonedTime(new Date(), timeZone);

  const duration = intervalToDuration({ start: now, end: targetDate });
  if (
    duration.days === undefined ||
    duration.hours === undefined ||
    duration.minutes === undefined ||
    duration.seconds === undefined
  )
    return 'No date provided';

  const hours = (duration.days * 24 + duration.hours)
    .toString()
    .padStart(2, '0');
  const minutes = duration.minutes.toString().padStart(2, '0');
  const seconds = duration.seconds.toString().padStart(2, '0');

  return `Your token will expire in ${hours}:${minutes}:${seconds}`;
}
