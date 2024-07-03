import * as React from 'react';
import { ContentBox } from '../../components/ContentBox';
import {
  Box,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  colors,
} from '@mui/material';
import {
  type GTFSFeedType,
  type AllFeedType,
} from '../../services/feeds/utils';

export interface AssociatedFeedsProps {
  feeds: AllFeedType[] | undefined;
}

const renderAssociatedGTFSFeedRow = (
  assocFeed: GTFSFeedType,
): JSX.Element | undefined => {
  if (assocFeed === undefined) {
    return undefined;
  }
  return (
    <TableRow
      key={assocFeed?.id}
      sx={{
        '&:hover': {
          backgroundColor: colors.grey[200],
        },
      }}
    >
      <a
        href={`/feeds/${assocFeed?.id}`}
        rel='noreferrer'
        style={{ display: 'contents' }}
      >
        <TableCell sx={{ paddingLeft: 0 }}>{assocFeed.feed_name}</TableCell>
        <TableCell sx={{ paddingRight: 0 }}>
          {assocFeed.latest_dataset?.downloaded_at !== undefined && (
            <span style={{ display: 'flex' }}>
              Last updated on{' '}
              {new Date(assocFeed.latest_dataset?.downloaded_at).toDateString()}
            </span>
          )}
        </TableCell>
      </a>
    </TableRow>
  );
};

export default function AssociatedGTFSRTFeeds({
  feeds,
}: AssociatedFeedsProps): React.ReactElement {
  return (
    <Box width={{ xs: '100%', md: '40%' }}>
      {feeds !== undefined && (
        <ContentBox
          width={{ xs: '100%' }}
          title={'Related Schedule Feeds'}
          outlineColor={colors.indigo[500]}
        >
          <TableContainer>
            <TableBody sx={{ display: 'inline-table', width: '100%' }}>
              {feeds
                .filter((assocFeed) => assocFeed?.data_type === 'gtfs')
                .map((assocFeed) =>
                  renderAssociatedGTFSFeedRow(assocFeed as GTFSFeedType),
                )}
            </TableBody>
          </TableContainer>
        </ContentBox>
      )}
    </Box>
  );
}
