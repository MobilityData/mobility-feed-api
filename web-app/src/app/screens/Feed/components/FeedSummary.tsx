import * as React from 'react';
import { ContentBox } from '../../../components/ContentBox';
import {
  Box,
  Button,
  Chip,
  Grid,
  Typography,
  Snackbar,
  IconButton,
  Tooltip,
  useTheme,
  Link,
} from '@mui/material';
import { ContentCopy, ContentCopyOutlined } from '@mui/icons-material';
import {
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../../services/feeds/utils';
import { type components } from '../../../services/feeds/types';
import { useTranslation } from 'react-i18next';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { getFeatureComponentDecorators } from '../../../utils/consts';
import PublicIcon from '@mui/icons-material/Public';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import LinkIcon from '@mui/icons-material/Link';
import DatasetIcon from '@mui/icons-material/Dataset';
import LayersIcon from '@mui/icons-material/Layers';
import EmailIcon from '@mui/icons-material/Email';
import DateRangeIcon from '@mui/icons-material/DateRange';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import { FeedStatusIndicator } from '../../../components/FeedStatus';
import Locations from '../../../components/Locations';
import { formatServiceDateRange } from '../Feed.functions';
import {
  boxElementStyle,
  StyledTitleContainer,
  boxElementStyleTransitProvider,
  ResponsiveListItem,
  boxElementStyleProducerURL,
  featureChipsStyle,
} from '../Feed.styles';
import FeedAuthenticationSummaryInfo from './FeedAuthenticationSummaryInfo';

export interface FeedSummaryProps {
  feed: GTFSFeedType | GTFSRTFeedType | undefined;
  sortedProviders: string[];
  latestDataset?: components['schemas']['GtfsDataset'] | undefined;
  width: Record<string, string>;
}

export default function FeedSummary({
  feed,
  sortedProviders,
  latestDataset,
  width,
}: FeedSummaryProps): React.ReactElement {
  const { t } = useTranslation('feeds');
  const theme = useTheme();
  const [snackbarOpen, setSnackbarOpen] = React.useState(false);
  const [showAllProviders, setShowAllProviders] = React.useState(false);
  const providersToDisplay = showAllProviders
    ? sortedProviders
    : sortedProviders.slice(0, 4);

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
            {t('locations')}
          </Typography>
        </StyledTitleContainer>
        <Box data-testid='location'>
          {feed?.locations != null && <Locations locations={feed?.locations} />}
        </Box>
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
      {latestDataset?.agency_timezone != undefined && (
        <Box sx={boxElementStyle}>
          <StyledTitleContainer>
            <AccessTimeIcon></AccessTimeIcon>
            <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
              Agency Timezone
            </Typography>
          </StyledTitleContainer>
          <Typography variant='body1'>
            {latestDataset.agency_timezone}
          </Typography>
        </Box>
      )}
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
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              {formatServiceDateRange(
                latestDataset?.service_date_range_start,
                latestDataset?.service_date_range_end,
                latestDataset.agency_timezone,
              )}
              <FeedStatusIndicator
                status={feed?.status ?? ''}
              ></FeedStatusIndicator>
            </Box>
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
              <Button
                variant='text'
                className='inline line-start'
                href={feed?.source_info?.producer_url}
                target='_blank'
                rel='noopener noreferrer'
              >
                {feed?.source_info?.producer_url}
              </Button>
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

      <FeedAuthenticationSummaryInfo feed={feed} />

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
                  component={Link}
                  label={feature}
                  variant='filled'
                  sx={featureChipsStyle}
                  clickable
                  target='_blank'
                  rel='noreferrer'
                  href={getFeatureComponentDecorators(feature)?.linkToInfo}
                />
              </Grid>
            ))}
          </Grid>
        </Box>
      )}
    </ContentBox>
  );
}
