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
import { OpenInNewOutlined } from '@mui/icons-material';
import { type GTFSRTFeedType } from '../../services/feeds/utils';

export interface AssociatedGTFSRTFeedsProps {
  feed: GTFSRTFeedType | undefined;
}

export default function AssociatedGTFSRTFeeds({
  feed,
}: AssociatedGTFSRTFeedsProps): React.ReactElement {
  return (
    <Box width={{ xs: '100%', md: '40%' }}>
      <ContentBox
        width={{ xs: '100%' }}
        title={'Related Schedule Feeds'}
        outlineColor={colors.indigo[500]}
      >
        <TableContainer>
          <TableBody>
            {feed?.data_type === 'gtfs_rt' &&
              feed?.feed_references?.map((feedRef) => {
                return (
                  <TableRow key={feedRef}>
                    <TableCell>
                      <span style={{ display: 'flex' }}>
                        <a href={`/feeds/${feedRef}`} rel='noreferrer'>
                          {feedRef}
                        </a>
                        <OpenInNewOutlined />
                      </span>
                    </TableCell>
                  </TableRow>
                );
              })}
          </TableBody>
        </TableContainer>
      </ContentBox>
    </Box>
  );
}
