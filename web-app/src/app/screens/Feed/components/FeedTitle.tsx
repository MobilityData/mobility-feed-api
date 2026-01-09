import { Typography } from '@mui/material';
import {
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../../services/feeds/utils';
import { getTranslations } from 'next-intl/server';

interface FeedTitleProps {
  sortedProviders: string[];
  feed: GTFSFeedType | GTFSRTFeedType;
}

export default async function FeedTitle({
  sortedProviders,
  feed,
}: FeedTitleProps): Promise<React.ReactElement> {
  const tCommon = await getTranslations('common');
  const mainProvider = sortedProviders[0];
  let extraProviders: string | undefined;
  let realtimeFeedName: string | undefined;
  if (sortedProviders.length > 1) {
    extraProviders =
      '+' + (sortedProviders.length - 1) + ' ' + tCommon('others');
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
      color='primary'
      sx={{
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
