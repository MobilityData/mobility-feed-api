import * as React from 'react';
import { ContentBox } from '../../components/ContentBox';
import {
  Box,
  Button,
  Chip,
  Grid,
  type SxProps,
  Typography,
  Snackbar,
  styled,
  IconButton,
  Tooltip,
} from '@mui/material';
import { ContentCopy, ContentCopyOutlined } from '@mui/icons-material';
import {
  getLocationName,
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';
import { type components } from '../../services/feeds/types';
import { useTranslation } from 'react-i18next';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { theme } from '../../Theme';
import { getDataFeatureUrl } from '../../utils/consts';
import PublicIcon from '@mui/icons-material/Public';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import LinkIcon from '@mui/icons-material/Link';
import DatasetIcon from '@mui/icons-material/Dataset';
import LayersIcon from '@mui/icons-material/Layers';
import EmailIcon from '@mui/icons-material/Email';
import LockIcon from '@mui/icons-material/Lock';
import DateRangeIcon from '@mui/icons-material/DateRange';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { FeedStatusIndicator } from '../../components/FeedStatus';

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

const boxElementStyleTransitProvider: SxProps = {
  width: '100%',
  mt: 2,
  borderBottom: 'none',
};

const boxElementStyleProducerURL: SxProps = {
  width: '100%',
  mb: 1,
};

const StyledTitleContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  gap: theme.spacing(1),
  marginBottom: '4px',
  marginTop: theme.spacing(3),
  alignItems: 'center',
}));

const ResponsiveListItem = styled('li')(({ theme }) => ({
  width: '100%',
  margin: '5px 0',
  fontWeight: 'normal',
  fontSize: '16px',
  [theme.breakpoints.up('lg')]: {
    width: 'calc(50% - 15px)',
  },
}));

const formatServiceDateRange = (
  dateStart: string,
  dateEnd: string,
): JSX.Element => {
  const startDate = new Date(dateStart);
  const endDate = new Date(dateEnd);
  const formattedDateStart = new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(startDate);
  const formattedDateEnd = new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(endDate);
  return (
    <Box>
      <Typography variant='body1'>
        {formattedDateStart}{' '}
        <Typography component={'span'} sx={{ mx: 2, fontSize: '14px' }}>
          -
        </Typography>{' '}
        {formattedDateEnd}
      </Typography>
    </Box>
  );
};

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
      outlineColor={theme.palette.primary.dark}
      padding={2}
    >
      <Box sx={boxElementStyle}>
        <StyledTitleContainer>
          <PublicIcon></PublicIcon>
          <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
            {t('location')}
          </Typography>
        </StyledTitleContainer>
        <Typography variant='body1' data-testid='location'>
          {getLocationName(feed?.locations)}
        </Typography>
      </Box>
      <Box sx={boxElementStyleTransitProvider}>
        <StyledTitleContainer>
          <DirectionsBusIcon></DirectionsBusIcon>
          <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
            {t('transitProvider')}
          </Typography>
        </StyledTitleContainer>
        <Box>
          <ul
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              paddingLeft: providersToDisplay.length <= 1 ? '0px' : '25px',
              justifyContent: 'space-between',
              marginTop: 0,
              maxHeight: '500px',
              overflowY: showAllProviders ? 'scroll' : 'hidden',
              borderBottom: showAllProviders ? '1px solid #e0e0e0' : 'none',
              borderTop: showAllProviders ? '1px solid #e0e0e0' : 'none',
              listStyle: providersToDisplay.length <= 1 ? 'none' : undefined,
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
      {latestDataset?.service_date_range_start != undefined &&
        latestDataset.service_date_range_end != undefined && (
          <Box sx={boxElementStyle}>
            <StyledTitleContainer>
              <DateRangeIcon></DateRangeIcon>
              <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
                {t('serviceDateRange')}
                <Tooltip title={t('serviceDateRangeTooltip')} placement='top'>
                  <IconButton>
                    <InfoOutlinedIcon />
                  </IconButton>
                </Tooltip>
              </Typography>
            </StyledTitleContainer>
            <Typography
              variant='body1'
              sx={{ display: 'flex', alignItems: 'center', gap: 3 }}
            >
              {formatServiceDateRange(
                latestDataset?.service_date_range_start,
                latestDataset?.service_date_range_end,
              )}
              <FeedStatusIndicator
                status={feed?.status ?? ''}
              ></FeedStatusIndicator>
            </Typography>
          </Box>
        )}
      <Box sx={boxElementStyleProducerURL}>
        <StyledTitleContainer>
          <LinkIcon></LinkIcon>
          <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
            {t('producerDownloadUrl')}
          </Typography>
        </StyledTitleContainer>
        <Box>
          <Typography
            sx={{ display: 'flex', overflowWrap: 'anywhere' }}
            data-testid='producer-url'
          >
            {feed?.source_info?.producer_url != undefined && (
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
        <StyledTitleContainer>
          <DatasetIcon></DatasetIcon>
          <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
            {t('dataType')}
          </Typography>
        </StyledTitleContainer>
        <Typography data-testid='data-type'>
          {feed?.data_type === 'gtfs' && t('common:gtfsSchedule')}
          {feed?.data_type === 'gtfs_rt' && t('common:gtfsRealtime')}
        </Typography>
      </Box>

      {feed?.source_info?.authentication_type !== 0 && (
        <Box sx={boxElementStyle}>
          <StyledTitleContainer>
            <LockIcon></LockIcon>
            <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
              {t('authenticationType')}
            </Typography>
            <Typography data-testid='data-type'>
              {feed?.source_info?.authentication_type === 1 &&
                t('common:apiKey')}
              {feed?.source_info?.authentication_type === 2 &&
                t('common:httpHeader')}
            </Typography>
          </StyledTitleContainer>
        </Box>
      )}

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
        feed?.feed_contact_email != undefined &&
        feed?.feed_contact_email.length > 0 && (
          <Box sx={boxElementStyle}>
            <StyledTitleContainer>
              <EmailIcon></EmailIcon>
              <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
                {t('feedContactEmail')}
              </Typography>
            </StyledTitleContainer>
            {feed?.feed_contact_email != undefined &&
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

      {latestDataset?.validation_report?.features != undefined && (
        <Box sx={boxElementStyle}>
          <StyledTitleContainer>
            <LayersIcon></LayersIcon>
            <Typography
              variant='subtitle1'
              sx={{ fontWeight: 'bold', display: 'flex' }}
            >
              {t('features')}
              <Tooltip title='More Info' placement='top'>
                <IconButton
                  href='https://gtfs.org/getting_started/features/overview/'
                  target='_blank'
                  rel='noopener noreferrer'
                  size='small'
                  sx={{ ml: 1 }}
                >
                  <OpenInNewIcon fontSize='small' />
                </IconButton>
              </Tooltip>
            </Typography>
          </StyledTitleContainer>

          <Grid container spacing={1}>
            {latestDataset.validation_report?.features?.map((feature) => (
              <Grid item key={feature} data-testid='feature-chips'>
                <Chip
                  label={feature}
                  variant='filled'
                  sx={{
                    color: '#fff',
                    backgroundColor: theme.palette.primary.dark,
                    ':hover': {
                      backgroundColor: theme.palette.primary.light,
                    },
                  }}
                  onClick={() => {
                    window.open(getDataFeatureUrl(feature), '_blank');
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
