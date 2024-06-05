import * as React from 'react';
import { ContentBox } from '../../components/ContentBox';
import {
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  colors,
} from '@mui/material';
import { ContentCopy, ContentCopyOutlined } from '@mui/icons-material';
import {
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';

export interface FeedSummaryProps {
  feed: GTFSFeedType | GTFSRTFeedType | undefined;
}

export default function FeedSummary({
  feed,
}: FeedSummaryProps): React.ReactElement {
  return (
    <ContentBox
      width={{ xs: '100%', md: '50%' }}
      title={'Feed Summary'}
      outlineColor={colors.indigo[500]}
    >
      <TableContainer>
        <Table>
          <TableBody>
            <TableRow>
              <TableCell
                sx={{ fontSize: 14, fontWeight: 'bold', border: 'none' }}
              >
                Producer download URL:
              </TableCell>
              <TableCell sx={{ border: 'none' }}>
                <Button
                  sx={{ textOverflow: 'ellipsis' }}
                  variant='outlined'
                  endIcon={<ContentCopy />}
                  onClick={() => {
                    if (feed?.source_info?.producer_url !== undefined) {
                      void navigator.clipboard
                        .writeText(feed?.source_info?.producer_url)
                        .then((value) => {});
                    }
                  }}
                >
                  {feed?.source_info?.producer_url}
                </Button>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell
                sx={{ fontSize: 14, fontWeight: 'bold', border: 'none' }}
              >
                Data type:
              </TableCell>
              <TableCell sx={{ border: 'none' }}>
                <Button sx={{ textOverflow: 'ellipsis' }} variant='outlined'>
                  {feed?.data_type === 'gtfs' && 'GTFS'}
                  {feed?.data_type === 'gtfs_rt' && 'GTFS Realtime'}
                </Button>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell
                sx={{ fontSize: 14, fontWeight: 'bold', border: 'none' }}
              >
                Location:
              </TableCell>
              <TableCell sx={{ border: 'none' }}>
                {feed?.locations !== undefined
                  ? Object.values(feed?.locations[0])
                      .filter((v) => v !== null)
                      .reverse()
                      .join(', ')
                  : ''}
              </TableCell>
            </TableRow>
            {feed?.data_type === 'gtfs' && (
              <TableRow>
                <TableCell
                  sx={{ fontSize: 14, fontWeight: 'bold', border: 'none' }}
                >
                  Last downloaded at:
                </TableCell>
                <TableCell sx={{ border: 'none' }}>
                  {feed?.data_type === 'gtfs' &&
                  feed.latest_dataset?.downloaded_at != null
                    ? new Date(
                        feed?.latest_dataset?.downloaded_at,
                      ).toUTCString()
                    : undefined}
                </TableCell>
              </TableRow>
            )}
            <TableRow>
              <TableCell
                sx={{ fontSize: 14, fontWeight: 'bold', border: 'none' }}
              >
                HTTP Auth Parameter:
              </TableCell>
              <TableCell sx={{ border: 'none' }}>
                {feed?.source_info?.api_key_parameter_name !== null
                  ? feed?.source_info?.api_key_parameter_name
                  : 'N/A'}
              </TableCell>
            </TableRow>
            {feed?.data_type === 'gtfs' && (
              <TableRow>
                <TableCell
                  sx={{ fontSize: 14, fontWeight: 'bold', border: 'none' }}
                >
                  Feed contact email:
                </TableCell>
                <TableCell sx={{ border: 'none' }}>
                  {feed?.feed_contact_email !== undefined &&
                    feed?.feed_contact_email.length > 0 && (
                      <Button
                        onClick={() => {
                          if (feed?.feed_contact_email !== undefined) {
                            void navigator.clipboard
                              .writeText(feed?.feed_contact_email)
                              .then((value) => {});
                          }
                        }}
                        sx={{ textOverflow: 'ellipsis' }}
                        variant='outlined'
                        endIcon={<ContentCopyOutlined />}
                      >
                        {feed?.feed_contact_email}
                      </Button>
                    )}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </ContentBox>
  );
}
