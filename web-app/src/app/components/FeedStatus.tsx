'use client';

import { Box, Chip, Tooltip, useTheme } from '@mui/material';
import { useTranslations } from 'next-intl';
import { getFeedStatusData } from '../utils/feedStatusConsts';

export interface FeedStatusProps {
  status: string;
  chipSize?: 'small' | 'medium';
  disableTooltip?: boolean;
}

export const FeedStatusIndicator = (
  props: React.PropsWithChildren<FeedStatusProps>,
): JSX.Element => {
  const t = useTranslations('feeds');
  const theme = useTheme();
  const statusData = getFeedStatusData(props.status, theme, t);
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
              minWidth: '12px',
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
  const t = useTranslations('feeds');
  const theme = useTheme();
  const statusData = getFeedStatusData(props.status, theme, t);
  return (
    <>
      {statusData != undefined && (
        <Tooltip
          title={
            props.disableTooltip != undefined && props.disableTooltip
              ? ''
              : statusData.toolTipLong
          }
          placement='top'
        >
          <Chip
            label={statusData.label}
            color={statusData.themeColor}
            size={props.chipSize ?? 'medium'}
          ></Chip>
        </Tooltip>
      )}
    </>
  );
};
