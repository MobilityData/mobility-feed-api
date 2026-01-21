'use client';

import * as React from 'react';
import { ContentBox } from '../../../components/ContentBox';
import {
  Box,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  Typography,
  useTheme,
} from '@mui/material';
import {
  type GTFSFeedType,
  type AllFeedType,
  type GTFSRTFeedType,
} from '../../../services/feeds/utils';
import NextLink from 'next/link';

export interface AssociatedFeedsProps {
  feeds: AllFeedType[] | undefined;
  gtfsRtFeeds: GTFSRTFeedType[] | undefined;
}

const renderAssociatedGTFSFeedRow = (
  assocFeed: GTFSFeedType,
): React.ReactElement | undefined => {
  const theme = useTheme();
  if (assocFeed === undefined) {
    return undefined;
  }
  const hasFeedName =
    assocFeed.feed_name !== undefined && assocFeed.feed_name !== '';
  const noLatestDataset = assocFeed.latest_dataset === undefined;
  return (
    <TableRow
      key={assocFeed?.id}
      component={NextLink}
      href={`/feeds/gtfs/${assocFeed?.id}`}
      sx={{
        textDecoration: 'none',
        '&:hover, &:focus': {
          backgroundColor: theme.palette.background.paper,
        },
      }}
    >
      <TableCell component={Box} sx={{ paddingLeft: 0 }}>
        {!hasFeedName && noLatestDataset
          ? 'GTFS Schedule feed'
          : hasFeedName
            ? assocFeed.feed_name
            : ''}
      </TableCell>
      <TableCell
        component={Box}
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
): React.ReactElement | undefined => {
  const theme = useTheme();
  if (assocGTFSRTFeed === undefined) {
    return undefined;
  }
  const hasFeedName =
    assocGTFSRTFeed.feed_name !== undefined && assocGTFSRTFeed.feed_name !== '';
  return (
    <TableRow
      key={assocGTFSRTFeed?.id}
      component={NextLink}
      href={`/feeds/gtfs_rt/${assocGTFSRTFeed?.id}`}
      sx={{
        textDecoration: 'none',
        '&:hover, &:focus': {
          backgroundColor: theme.palette.background.paper,
        },
      }}
    >
      <TableCell sx={{ paddingLeft: 0 }} component={Box}>
        {hasFeedName ? assocGTFSRTFeed.feed_name : assocGTFSRTFeed.provider}
      </TableCell>
      {assocGTFSRTFeed.entity_types !== undefined && (
        <TableCell
          component={Box}
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
  const theme = useTheme();
  const gtfsFeeds =
    feeds?.filter((assocFeed) => assocFeed?.data_type === 'gtfs') ?? [];
  return (
    <Box width={{ xs: '100%' }}>
      <ContentBox
        width={{ xs: '100%' }}
        title={'Related Schedule Feeds'}
        outlineColor={theme.palette.background.default}
        margin={`0 0 ${theme.spacing(2)}`}
        padding={2}
      >
        {feeds === undefined && <Typography>Loading...</Typography>}
        {feeds !== undefined && gtfsFeeds?.length === 0 && (
          <Typography sx={{ mt: 1 }}>No associated feeds found.</Typography>
        )}
        {feeds !== undefined && gtfsFeeds.length > 0 && (
          <TableContainer component={Box}>
            <TableBody
              component={Box}
              sx={{ display: 'inline-table', width: '100%' }}
            >
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
        outlineColor={theme.palette.background.default}
        padding={2}
      >
        {gtfsRtFeeds === undefined && <Typography>Loading...</Typography>}
        {gtfsRtFeeds !== undefined && gtfsRtFeeds?.length === 0 && (
          <Typography sx={{ mt: 1 }}>No associated feeds found.</Typography>
        )}
        {gtfsRtFeeds !== undefined && gtfsRtFeeds.length > 0 && (
          <TableContainer component={Box}>
            <TableBody
              component={Box}
              sx={{ display: 'inline-table', width: '100%' }}
            >
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
