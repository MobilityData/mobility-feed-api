import { type TFunction } from 'i18next';

export function formatProvidersSorted(provider: string): string[] {
  const providers = provider.split(',').filter((n) => n);
  const providersTrimmed = providers.map((p) => p.trim());
  const providersSorted = providersTrimmed.sort();
  return providersSorted;
}

export function getFeedFormattedName(
  sortedProviders: string[],
  dataType: 'gtfs' | 'gtfs_rt',
  feedName?: string,
): string {
  let formattedName = '';
  if (sortedProviders[0] !== undefined && sortedProviders[0] !== '') {
    formattedName += sortedProviders[0];
  }
  if (feedName !== undefined && feedName !== '') {
    if (formattedName !== '') {
      formattedName += ', ';
    }
    formattedName += `${feedName}`;
  }
  return formattedName;
}

export function generateDescriptionMetaTag(
  t: TFunction<'feeds'>,
  sortedProviders: string[],
  dataType: 'gtfs' | 'gtfs_rt',
  feedName?: string,
): string {
  const formattedName = getFeedFormattedName(
    sortedProviders,
    dataType,
    feedName,
  );
  if (
    sortedProviders.length === 0 &&
    (feedName === undefined || feedName === '')
  ) {
    return '';
  }
  const dataTypeVerbose =
    dataType === 'gtfs' ? t('common:gtfsSchedule') : t('common:gtfsRealtime');
  return t('detailPageDescription', { formattedName, dataTypeVerbose });
}

export function generatePageTitle(
  sortedProviders: string[],
  dataType: 'gtfs' | 'gtfs_rt',
  feedName?: string,
): string {
  let newDocTitle = getFeedFormattedName(sortedProviders, dataType, feedName);
  const dataTypeVerbose = dataType === 'gtfs' ? 'Schedule' : 'Realtime';

  if (newDocTitle !== '') {
    newDocTitle += ` GTFS ${dataTypeVerbose} Feed - `;
  }

  newDocTitle += 'Mobility Database';
  return newDocTitle;
}
