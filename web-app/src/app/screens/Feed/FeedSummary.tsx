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
  styled,
} from '@mui/material';
import { ContentCopy, ContentCopyOutlined } from '@mui/icons-material';
import {
  getLocationName,
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';
import { type components } from '../../services/feeds/types';
import { useTranslation } from 'react-i18next';

export interface FeedSummaryProps {
  feed: GTFSFeedType | GTFSRTFeedType | undefined;
  sortedProviders: string[];
  latestDataset?: components['schemas']['GtfsDataset'] | undefined;
  width: Record<string, string>;
}

const boxElementStyle: SxProps = {
  width: '100%',
  mt: 2,
  mb: 1,
};

const ResponsiveListItem = styled('li')(({ theme }) => ({
  width: '100%',
  margin: '5px 0',
  fontWeight: 'normal',
  fontSize: '16px',
  [theme.breakpoints.up('lg')]: {
    width: 'calc(50% - 15px)',
  },
}));

export default function FeedSummary({
  feed,
  sortedProviders,
  latestDataset,
  width,
}: FeedSummaryProps): React.ReactElement {
  const { t } = useTranslation('feeds');
  const [snackbarOpen, setSnackbarOpen] = React.useState(false);
  const [showAllProviders, setShowAllProviders] = React.useState(false);
  const providersToDisplay = showAllProviders
    ? sortedProviders
    : sortedProviders.slice(0, 4);

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
          {t('location')}
        </Typography>
        <Typography variant='body1' data-testid='location'>
          {getLocationName(feed?.locations)}
        </Typography>
      </Box>
      <Box sx={boxElementStyle}>
        <Typography
          variant='subtitle1'
          gutterBottom
          sx={{ fontWeight: 'bold' }}
        >
          {t('transitProvider')}
        </Typography>
        <Box>
          <ul
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              paddingLeft: '25px',
              justifyContent: 'space-between',
              marginTop: 0,
              maxHeight: '500px',
              overflowY: showAllProviders ? 'scroll' : 'hidden',
              borderBottom: showAllProviders ? '1px solid #e0e0e0' : 'none',
              borderTop: showAllProviders ? '1px solid #e0e0e0' : 'none',
            }}
          >
            {providersToDisplay.map((provider) => (
              <ResponsiveListItem key={provider}>{provider}</ResponsiveListItem>
            ))}
          </ul>

          {!showAllProviders && sortedProviders.length > 4 && (
            <Button
              variant='text'
              onClick={() => {
                setShowAllProviders(true);
              }}
            >
              {t('seeFullList')}
            </Button>
          )}

          {showAllProviders && (
            <Button
              variant='text'
              onClick={() => {
                setShowAllProviders(false);
              }}
            >
              {t('hideFullList')}
            </Button>
          )}
        </Box>
      </Box>
      <Box sx={boxElementStyle}>
        <Typography
          variant='subtitle1'
          gutterBottom
          sx={{ fontWeight: 'bold' }}
        >
          {t('producerDownloadUrl')}
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
              titleAccess={t('copyDownloadUrl')}
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
            message={t('producerUrlCopied')}
          />
        </Box>
      </Box>

      <Box sx={boxElementStyle}>
        <Typography
          variant='subtitle1'
          gutterBottom
          sx={{ fontWeight: 'bold' }}
        >
          {t('dataType')}
        </Typography>
        <Typography data-testid='data-type'>
          {feed?.data_type === 'gtfs' && t('common:gtfsSchedule')}
          {feed?.data_type === 'gtfs_rt' && t('common:gtfsRealtime')}
        </Typography>
      </Box>

      <Box sx={boxElementStyle}>
        <Typography
          variant='subtitle1'
          gutterBottom
          sx={{ fontWeight: 'bold' }}
        >
          {t('authenticationType')}
        </Typography>
        <Typography data-testid='data-type'>
          {feed?.source_info?.authentication_type === 1 && t('common:apiKey')}
          {feed?.source_info?.authentication_type === 2 &&
            t('common:httpHeader')}
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
            {t('registerToDownloadFeed')}
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
              {t('feedContactEmail')}:
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
                      titleAccess={t('copyFeedContactEmail')}
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
            {t('features')}
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
