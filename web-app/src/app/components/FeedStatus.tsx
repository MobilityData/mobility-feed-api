import { Box, Chip, Tooltip, useTheme } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { type TFunction } from 'i18next';

export interface FeedStatusProps {
  status: string;
}

interface FeedStatusData {
  toolTip: string;
  label: string;
  themeColor: 'success' | 'info' | 'warning' | 'error';
  toolTipLong: string;
}

function getFeedStatusData(
  status: string,
  t: TFunction,
): FeedStatusData | undefined {
  const data: Record<string, FeedStatusData> = {
    active: {
      toolTip: t('feedStatus.active.toolTip'),
      label: t('feedStatus.active.label'),
      themeColor: 'success',
      toolTipLong: t('feedStatus.active.toolTipLong'),
    },
    future: {
      toolTip: t('feedStatus.future.toolTip'),
      label: t('feedStatus.future.label'),
      themeColor: 'info',
      toolTipLong: t('feedStatus.future.toolTipLong'),
    },
    inactive: {
      toolTip: t('feedStatus.inactive.toolTip'),
      label: t('feedStatus.inactive.label'),
      themeColor: 'warning',
      toolTipLong: t('feedStatus.inactive.toolTipLong'),
    },
    deprecated: {
      toolTip: t('feedStatus.deprecated.toolTip'),
      label: t('feedStatus.deprecated.label'),
      themeColor: 'error',
      toolTipLong: t('feedStatus.deprecated.toolTipLong'),
    },
  };

  return data[status];
}

export const FeedStatusIndicator = (
  props: React.PropsWithChildren<FeedStatusProps>,
): JSX.Element => {
  const { t } = useTranslation('feeds');
  const theme = useTheme();
  const statusData = getFeedStatusData(props.status, t);
  return (
    <>
      {statusData != undefined && (
        <Tooltip title={statusData.toolTip} placement='top'>
          <Box
            sx={{
              background: theme.palette[statusData.themeColor].main,
              width: '12px',
              height: '12px',
              borderRadius: '50%',
            }}
          ></Box>
        </Tooltip>
      )}
    </>
  );
};

export const FeedStatusChip = (
  props: React.PropsWithChildren<FeedStatusProps>,
): JSX.Element => {
  const { t } = useTranslation('feeds');
  const statusData = getFeedStatusData(props.status, t);
  return (
    <>
      {statusData != undefined && (
        <Tooltip title={statusData.toolTipLong} placement='top'>
          <Chip label={statusData.label} color={statusData.themeColor}></Chip>
        </Tooltip>
      )}
    </>
  );
};
