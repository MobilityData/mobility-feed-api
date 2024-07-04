import * as React from 'react';
import { ContentBox } from '../../components/ContentBox';
import {
  Box,
  Button,
  Chip,
  Grid,
  type SxProps,
  Typography,
  colors,
  Snackbar,
} from '@mui/material';
import { ContentCopy, ContentCopyOutlined } from '@mui/icons-material';
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

const boxElementStyle: SxProps = {
  width: '100%',
  mt: 2,
  mb: 1,
};

export default function FeedSummary({
  feed,
  latestDataset,
  width,
}: FeedSummaryProps): React.ReactElement {
  const [snackbarOpen, setSnackbarOpen] = React.useState(false);

  return (
    <ContentBox
      width={width}
      title={'Feed Summary'}
      outlineColor={colors.indigo[500]}
      padding={2}
    >
      <Box sx={boxElementStyle}>
        <Typography
          variant='subtitle1'
          gutterBottom
          sx={{ fontWeight: 'bold' }}
        >
          Location
        </Typography>
        <Typography variant='body1'>
          {feed?.locations !== undefined
            ? Object.values(feed?.locations[0])
                .filter((v) => v !== null)
                .reverse()
                .join(', ')
            : ''}
        </Typography>
      </Box>
      <Box sx={boxElementStyle}>
        <Typography
          variant='subtitle1'
          gutterBottom
          sx={{ fontWeight: 'bold' }}
        >
          Producer download URL
        </Typography>
        <Box>
          <Typography sx={{ display: 'flex', overflowWrap: 'anywhere' }}>
            {feed?.source_info?.producer_url}
            <ContentCopy
              titleAccess='Copy download URL'
              sx={{ cursor: 'pointer', ml: 1 }}
              onClick={() => {
                if (feed?.source_info?.producer_url !== undefined) {
                  setSnackbarOpen(true);
                  void navigator.clipboard
                    .writeText(feed?.source_info?.producer_url)
                    .then((value) => {});
                }
              }}
            />
          </Typography>
          <Button
            sx={{ mt: 1 }}
            variant='contained'
            disableElevation
            onClick={() => {
              if (feed?.source_info?.producer_url !== undefined) {
                window.open(
                  feed?.source_info?.producer_url,
                  '_blank',
                  'rel=noopener noreferrer',
                );
              }
            }}
          >
            Download
          </Button>
          <Snackbar
            anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            open={snackbarOpen}
            autoHideDuration={5000}
            onClose={() => setSnackbarOpen(false)}
            message="Producer url copied to clipboard"
          />
        </Box>
      </Box>

      <Box sx={boxElementStyle}>
        <Typography
          variant='subtitle1'
          gutterBottom
          sx={{ fontWeight: 'bold' }}
        >
          Data type
        </Typography>
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
      </Box>

      {feed?.data_type === 'gtfs' &&
        feed?.feed_contact_email !== undefined &&
        feed?.feed_contact_email.length > 0 && (
          <Box sx={boxElementStyle}>
            <Typography
              variant='subtitle1'
              gutterBottom
              sx={{ fontWeight: 'bold' }}
            >
              Feed contact email:
            </Typography>
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
          </Box>
        )}

      {latestDataset?.validation_report?.features !== undefined && (
        <Box sx={boxElementStyle}>
          <Typography
            variant='subtitle1'
            gutterBottom
            sx={{ fontWeight: 'bold' }}
          >
            Features
          </Typography>
          <Grid container spacing={1}>
            {latestDataset.validation_report?.features?.map((feature) => (
              <Grid item key={feature}>
                <Chip
                  label={feature}
                  variant='filled'
                  sx={{
                    color: '#fff',
                    backgroundColor: colors.blue[900],
                  }}
                />
              </Grid>
            ))}
          </Grid>
        </Box>
      )}
    </ContentBox>
  );
}
