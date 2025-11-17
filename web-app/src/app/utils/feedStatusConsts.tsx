import { type Theme } from '@mui/material';
import { type TFunction } from 'i18next';

export interface FeedStatusData {
  toolTip: string;
  label: string;
  themeColor: 'success' | 'info' | 'warning' | 'error';
  color: string;
  toolTipLong: string;
}

export function getFeedStatusData(
  status: string,
  theme: Theme,
  t: TFunction,
): FeedStatusData | undefined {
  const data: Record<string, FeedStatusData> = {
    active: {
      toolTip: t('feedStatus.active.toolTip'),
      label: t('feedStatus.active.label'),
      themeColor: 'success',
      color: theme.palette.success.main,
      toolTipLong: t('feedStatus.active.toolTipLong'),
    },
    future: {
      toolTip: t('feedStatus.future.toolTip'),
      label: t('feedStatus.future.label'),
      themeColor: 'info',
      color: theme.palette.info.main,
      toolTipLong: t('feedStatus.future.toolTipLong'),
    },
    inactive: {
      toolTip: t('feedStatus.inactive.toolTip'),
      label: t('feedStatus.inactive.label'),
      themeColor: 'warning',
      color: theme.palette.warning.main,
      toolTipLong: t('feedStatus.inactive.toolTipLong'),
    },
    deprecated: {
      toolTip: t('feedStatus.deprecated.toolTip'),
      label: t('feedStatus.deprecated.label'),
      themeColor: 'error',
      color: theme.palette.error.main,
      toolTipLong: t('feedStatus.deprecated.toolTipLong'),
    },
  };

  return data[status];
}
