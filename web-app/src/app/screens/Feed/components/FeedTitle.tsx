'use client';

import { Typography, useTheme } from '@mui/material';
import {
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../../services/feeds/utils';
import { useTranslations } from 'next-intl';

interface FeedTitleProps {
  sortedProviders: string[];
  feed: GTFSFeedType | GTFSRTFeedType;
}

export default function FeedTitle({
  sortedProviders,
  feed,
}: FeedTitleProps): React.ReactElement {
  const t = useTranslations('feeds');
  const theme = useTheme();
  const mainProvider = sortedProviders[0];
  let extraProviders: string | undefined;
  let realtimeFeedName: string | undefined;
  if (sortedProviders.length > 1) {
    extraProviders =
      '+' + (sortedProviders.length - 1) + ' ' + t('common:others');
  }
  if (
    feed?.data_type === 'gtfs_rt' &&
    feed?.feed_name != undefined &&
    feed?.feed_name !== ''
  ) {
    realtimeFeedName = ` - ${feed?.feed_name}`;
  }
  return (
    <Typography
      component='h1'
      sx={{
        color: theme.palette.primary.main,
        fontWeight: 'bold',
        fontSize: { xs: 24, sm: 36 },
        lineHeight: 'normal',
      }}
      data-testid='feed-provider'
    >
      {mainProvider + (realtimeFeedName ?? '')}
      {extraProviders != undefined && (
        <Typography
          component={'span'}
          sx={{
            fontSize: { xs: 16, sm: 24 },
            ml: 1,
          }}
        >
          {extraProviders}
        </Typography>
      )}
    </Typography>
  );
}
