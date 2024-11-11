import * as React from 'react';
import { ContentBox } from '../../components/ContentBox';
import {
  Box,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  Typography,
} from '@mui/material';
import {
  type GTFSFeedType,
  type AllFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';
import { theme } from '../../Theme';

export interface AssociatedFeedsProps {
  feeds: AllFeedType[] | undefined;
  gtfsRtFeeds: GTFSRTFeedType[] | undefined;
}

const renderAssociatedGTFSFeedRow = (
  assocFeed: GTFSFeedType,
): JSX.Element | undefined => {
  if (assocFeed === undefined) {
    return undefined;
  }
  const hasFeedName =
    assocFeed.feed_name !== undefined && assocFeed.feed_name !== '';
  const noLatestDataset = assocFeed.latest_dataset === undefined;
  return (
    <TableRow
      key={assocFeed?.id}
      component={'a'}
      href={`/feeds/${assocFeed?.id}`}
      sx={{
        textDecoration: 'none',
        '&:hover, &:focus': {
          backgroundColor: theme.palette.background.paper,
        },
      }}
    >
      <TableCell sx={{ paddingLeft: 0 }}>
        {!hasFeedName && noLatestDataset
          ? 'GTFS Schedule feed'
          : hasFeedName
            ? assocFeed.feed_name
            : ''}
      </TableCell>
      <TableCell
        sx={{ paddingRight: 0, paddingLeft: hasFeedName ? 'initial' : 0 }}
      >
        {assocFeed.latest_dataset?.downloaded_at !== undefined && (
          <span style={{ display: 'flex' }}>
            Last updated on{' '}
            {new Date(assocFeed.latest_dataset?.downloaded_at).toDateString()}
          </span>
        )}
      </TableCell>
    </TableRow>
  );
};

const renderAssociatedGTFSRTFeedRow = (
  assocGTFSRTFeed: GTFSRTFeedType,
): JSX.Element | undefined => {
  if (assocGTFSRTFeed === undefined) {
    return undefined;
  }
  const hasFeedName =
    assocGTFSRTFeed.feed_name !== undefined && assocGTFSRTFeed.feed_name !== '';
  return (
    <TableRow
      href={`/feeds/${assocGTFSRTFeed?.id}`}
      key={assocGTFSRTFeed?.id}
      component={'a'}
      sx={{
        textDecoration: 'none',
        '&:hover, &:focus': {
          backgroundColor: theme.palette.background.paper,
        },
      }}
    >
      <TableCell sx={{ paddingLeft: 0 }}>
        {hasFeedName ? assocGTFSRTFeed.feed_name : assocGTFSRTFeed.provider}
      </TableCell>
      {assocGTFSRTFeed.entity_types !== undefined && (
        <TableCell
          sx={{ paddingRight: 0, paddingLeft: hasFeedName ? 'initial' : 0 }}
        >
          {assocGTFSRTFeed.entity_types
            .map(
              (entityType) =>
                ({
                  tu: 'Trip Updates',
                  vp: 'Vehicle Positions',
                  sa: 'Service Alerts',
                })[entityType],
            )
            .join(' and ')}
        </TableCell>
      )}
    </TableRow>
  );
};

export default function AssociatedGTFSRTFeeds({
  feeds,
  gtfsRtFeeds,
}: AssociatedFeedsProps): React.ReactElement {
  const gtfsFeeds =
    feeds?.filter((assocFeed) => assocFeed?.data_type === 'gtfs') ?? [];
  return (
    <Box width={{ xs: '100%', md: '40%' }}>
      <ContentBox
        width={{ xs: '100%' }}
        title={'Related Schedule Feeds'}
        outlineColor={theme.palette.primary.dark}
        margin={'0 0 8px'}
        padding={2}
      >
        {feeds === undefined && <Typography>Loading...</Typography>}
        {feeds !== undefined && gtfsFeeds?.length === 0 && (
          <Typography sx={{ mt: 1 }}>No associated feeds found.</Typography>
        )}
        {feeds !== undefined && gtfsFeeds.length > 0 && (
          <TableContainer>
            <TableBody sx={{ display: 'inline-table', width: '100%' }}>
              {gtfsFeeds?.map((assocFeed) =>
                renderAssociatedGTFSFeedRow(assocFeed as GTFSFeedType),
              )}
            </TableBody>
          </TableContainer>
        )}
      </ContentBox>
      <ContentBox
        width={{ xs: '100%' }}
        title={'Related Realtime Feeds'}
        outlineColor={theme.palette.primary.dark}
        padding={2}
      >
        {gtfsRtFeeds === undefined && <Typography>Loading...</Typography>}
        {gtfsRtFeeds !== undefined && gtfsRtFeeds?.length === 0 && (
          <Typography sx={{ mt: 1 }}>No associated feeds found.</Typography>
        )}
        {gtfsRtFeeds !== undefined && gtfsRtFeeds.length > 0 && (
          <TableContainer>
            <TableBody sx={{ display: 'inline-table', width: '100%' }}>
              {gtfsRtFeeds?.map((assocGTFSRTFeed) =>
                renderAssociatedGTFSRTFeedRow(assocGTFSRTFeed),
              )}
            </TableBody>
          </TableContainer>
        )}
      </ContentBox>
    </Box>
  );
}
