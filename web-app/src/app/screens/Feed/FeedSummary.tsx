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

  const hasAuthenticationInfo =
    feed?.source_info?.authentication_info_url !== undefined &&
    feed?.source_info.authentication_info_url.trim() !== '';

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
        <Typography variant='body1' data-testid='location'>
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
          <Typography
            sx={{ display: 'flex', overflowWrap: 'anywhere' }}
            data-testid='producer-url'
          >
            {feed?.source_info?.producer_url !== undefined && (
              <a
                href={feed?.source_info?.producer_url}
                target='_blank'
                rel='noopener noreferrer'
                style={{ textDecoration: 'none' }}
              >
                {feed?.source_info?.producer_url}
              </a>
            )}
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
          <Snackbar
            anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            open={snackbarOpen}
            autoHideDuration={5000}
            onClose={() => {
              setSnackbarOpen(false);
            }}
            message='Producer url copied to clipboard'
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
        <Typography data-testid='data-type'>
          {feed?.data_type === 'gtfs' && 'GTFS Schedule'}
          {feed?.data_type === 'gtfs_rt' && 'GTFS Realtime'}
        </Typography>
      </Box>

      <Box sx={boxElementStyle}>
        <Typography
          variant='subtitle1'
          gutterBottom
          sx={{ fontWeight: 'bold' }}
        >
          Authentication type
        </Typography>
        <Typography data-testid='data-type'>
          {feed?.source_info?.authentication_type === 1 && 'API Key'}
          {feed?.source_info?.authentication_type === 2 && 'HTTP Header'}
        </Typography>
      </Box>

      {hasAuthenticationInfo && (
        <Button disableElevation variant='contained' sx={{ marginRight: 2 }}>
          <a
            href={feed?.source_info?.authentication_info_url}
            target='_blank'
            className='btn-link'
            rel='noreferrer'
          >
            Register to download this feed
          </a>
        </Button>
      )}

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
              <Grid item key={feature} data-testid='feature-chips'>
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
