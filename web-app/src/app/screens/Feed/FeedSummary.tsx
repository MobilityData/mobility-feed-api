import * as React from 'react';
import { ContentBox } from '../../components/ContentBox';
import {
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  colors,
} from '@mui/material';
import {
  ContentCopy,
  ContentCopyOutlined,
  Download,
} from '@mui/icons-material';
import {
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';
import { type components } from '../../services/feeds/types';

export interface FeedSummaryProps {
  feed: GTFSFeedType | GTFSRTFeedType | undefined;
  latestDataset?: components['schemas']['GtfsDataset'] | undefined;
  width: Record<string, string>;
}

export default function FeedSummary({
  feed,
  latestDataset,
  width,
}: FeedSummaryProps): React.ReactElement {
  return (
    <ContentBox
      width={width}
      title={'Feed Summary'}
      outlineColor={colors.indigo[500]}
    >
      <TableContainer>
        <Table>
          <TableBody>
            <TableRow>
              <TableCell sx={{ fontSize: 14, border: 'none' }}>
                <b>Location:</b>
                <div>
                  {feed?.locations !== undefined
                    ? Object.values(feed?.locations[0])
                        .filter((v) => v !== null)
                        .reverse()
                        .join(', ')
                    : ''}
                </div>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell sx={{ fontSize: 14, border: 'none' }}>
                <b>Producer download URL:</b>
                <div>
                  <Button
                    sx={{ textOverflow: 'ellipsis', cursor: 'initial' }}
                    variant='outlined'
                    disableRipple={true}
                    disableFocusRipple={true}
                    focusRipple={false}
                    endIcon={
                      <>
                        <Download
                          titleAccess='Download feed'
                          sx={{ cursor: 'pointer' }}
                          onClick={() => {
                            if (feed?.source_info?.producer_url !== undefined) {
                              window.open(
                                feed?.source_info?.producer_url,
                                '_blank',
                                'rel=noopener noreferrer',
                              );
                            }
                          }}
                        />
                        <ContentCopy
                          titleAccess='Copy download URL'
                          sx={{ cursor: 'pointer' }}
                          onClick={() => {
                            if (feed?.source_info?.producer_url !== undefined) {
                              void navigator.clipboard
                                .writeText(feed?.source_info?.producer_url)
                                .then((value) => {});
                            }
                          }}
                        />
                      </>
                    }
                  >
                    {feed?.source_info?.producer_url}
                  </Button>
                </div>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell sx={{ fontSize: 14, border: 'none' }}>
                <b>Data type:</b>
                <div>
                  <Button
                    sx={{ textOverflow: 'ellipsis', cursor: 'text' }}
                    variant='outlined'
                    disableRipple={true}
                    disableFocusRipple={true}
                    focusRipple={false}
                  >
                    {feed?.data_type === 'gtfs' && 'GTFS Schedule'}
                    {feed?.data_type === 'gtfs_rt' && 'GTFS Realtime'}
                  </Button>
                </div>
              </TableCell>
            </TableRow>
            {feed?.data_type === 'gtfs' &&
              feed?.feed_contact_email !== undefined &&
              feed?.feed_contact_email.length > 0 && (
                <TableRow>
                  <TableCell sx={{ fontSize: 14, border: 'none' }}>
                    <b>Feed contact email:</b>
                    <div>
                      {feed?.feed_contact_email !== undefined &&
                        feed?.feed_contact_email.length > 0 && (
                          <Button
                            sx={{ textOverflow: 'ellipsis', cursor: 'initial' }}
                            variant='outlined'
                            disableRipple={true}
                            disableFocusRipple={true}
                            focusRipple={false}
                            endIcon={
                              <ContentCopyOutlined
                                titleAccess='Copy feed contact email'
                                sx={{ cursor: 'pointer' }}
                                onClick={() => {
                                  if (feed?.feed_contact_email !== undefined) {
                                    void navigator.clipboard
                                      .writeText(feed?.feed_contact_email)
                                      .then((value) => {});
                                  }
                                }}
                              />
                            }
                          >
                            {feed?.feed_contact_email}
                          </Button>
                        )}
                    </div>
                  </TableCell>
                </TableRow>
              )}
            {latestDataset?.validation_report?.features !== undefined && (
              <TableRow>
                <TableCell sx={{ fontSize: 14, border: 'none' }}>
                  <b>Features</b>
                  <div>
                    {latestDataset.validation_report?.features?.map(
                      (feature) => (
                        <Chip
                          key={feature}
                          label={feature}
                          color='primary'
                          variant='filled'
                        />
                      ),
                    )}
                  </div>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </ContentBox>
  );
}
