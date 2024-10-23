import * as React from 'react';
import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useSelector } from 'react-redux';
import {
  Box,
  Container,
  CssBaseline,
  Typography,
  Button,
  Grid,
  colors,
} from '@mui/material';
import { ChevronLeft } from '@mui/icons-material';
import '../../styles/SignUp.css';
import '../../styles/FAQ.css';
import { ContentBox } from '../../components/ContentBox';
import { useAppDispatch } from '../../hooks';
import { loadingFeed, loadingRelatedFeeds } from '../../store/feed-reducer';
import {
  selectIsAnonymous,
  selectIsAuthenticated,
  selectUserProfile,
} from '../../store/profile-selectors';
import {
  selectFeedData,
  selectFeedLoadingStatus,
  selectGTFSFeedData,
  selectGTFSRTFeedData,
  selectRelatedFeedsData,
  selectRelatedGtfsRTFeedsData,
} from '../../store/feed-selectors';
import { clearDataset, loadingDataset } from '../../store/dataset-reducer';
import {
  selectBoundingBoxFromLatestDataset,
  selectDatasetsData,
  selectDatasetsLoadingStatus,
  selectLatestDatasetsData,
} from '../../store/dataset-selectors';
import { Map } from '../../components/Map';
import PreviousDatasets from './PreviousDatasets';
import FeedSummary from './FeedSummary';
import DataQualitySummary from './DataQualitySummary';
import AssociatedFeeds from './AssociatedFeeds';
import { WarningContentBox } from '../../components/WarningContentBox';
import {
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';
import { Trans, useTranslation } from 'react-i18next';
import { type TFunction } from 'i18next';

export function formatProvidersSorted(provider: string): string[] {
  const providers = provider.split(',').filter((n) => n);
  const providersTrimmed = providers.map((p) => p.trim());
  const providersSorted = providersTrimmed.sort();
  return providersSorted;
}

export function getFeedTitleElement(
  sortedProviders: string[],
  feed: GTFSFeedType | GTFSRTFeedType,
  translationFunction: TFunction<'feeds', undefined>,
): JSX.Element {
  const mainProvider = sortedProviders[0];
  let extraProviders: string | undefined;
  let realtimeFeedName: string | undefined;
  if (sortedProviders.length > 1) {
    extraProviders =
      '+' +
      (sortedProviders.length - 1) +
      ' ' +
      translationFunction('common:others');
  }
  if (
    feed?.data_type === 'gtfs_rt' &&
    feed?.feed_name !== undefined &&
    feed?.feed_name !== ''
  ) {
    realtimeFeedName = ` - ${feed?.feed_name}`;
  }
  return (
    <Typography
      sx={{
        color: colors.blue.A700,
        fontWeight: 'bold',
        fontSize: { xs: 24, sm: 36 },
        lineHeight: 'normal',
      }}
      data-testid='feed-provider'
    >
      {mainProvider + (realtimeFeedName ?? '')}
      {extraProviders !== undefined && (
        <Typography
          component={'span'}
          sx={{
            fontSize: { xs: 16, sm: 24 },
            ml: 1,
          }}
        >
          {extraProviders}
        </Typography>
      )}
    </Typography>
  );
}

const wrapComponent = (
  feedLoadingStatus: string,
  child: React.ReactElement,
): React.ReactElement => {
  const { t } = useTranslation('feeds');
  return (
    <Container
      component='main'
      sx={{ width: '100%', m: 'auto', px: 0 }}
      maxWidth='xl'
    >
      <CssBaseline />
      <Box
        sx={{ mt: 12, display: 'flex', flexDirection: 'column' }}
        margin={{ xs: '20px 0px' }}
      >
        <Box
          sx={{
            width: '100%',
            background: '#F8F5F5',
            borderRadius: '6px 0px 0px 6px',
            p: 3,
            color: 'black',
            fontSize: '18px',
            fontWeight: 700,
            mt: 4,
          }}
        >
          {feedLoadingStatus === 'error' && <>{t('errorLoadingFeed')}</>}
          {feedLoadingStatus !== 'error' ? child : null}
        </Box>
      </Box>
    </Container>
  );
};

export default function Feed(): React.ReactElement {
  const { t } = useTranslation('feeds');
  const dispatch = useAppDispatch();
  const { feedId } = useParams();
  const user = useSelector(selectUserProfile);
  const feedLoadingStatus = useSelector(selectFeedLoadingStatus);
  const datasetLoadingStatus = useSelector(selectDatasetsLoadingStatus);
  const feedType = useSelector(selectFeedData)?.data_type;
  const relatedFeeds = useSelector(selectRelatedFeedsData);
  const relatedGtfsRtFeeds = useSelector(selectRelatedGtfsRTFeedsData);
  const datasets = useSelector(selectDatasetsData);
  const latestDataset = useSelector(selectLatestDatasetsData);
  const boundingBox = useSelector(selectBoundingBoxFromLatestDataset);
  const feed =
    feedType === 'gtfs'
      ? useSelector(selectGTFSFeedData)
      : useSelector(selectGTFSRTFeedData);
  const needsToLoadFeed = feed === undefined || feed?.id !== feedId;
  const isAuthenticatedOrAnonymous =
    useSelector(selectIsAuthenticated) || useSelector(selectIsAnonymous);
  const sortedProviders = formatProvidersSorted(feed?.provider ?? '');

  useEffect(() => {
    if (user !== undefined && feedId !== undefined && needsToLoadFeed) {
      dispatch(clearDataset());
      dispatch(loadingFeed({ feedId }));
    }
  }, [isAuthenticatedOrAnonymous, needsToLoadFeed]);

  useEffect(() => {
    if (needsToLoadFeed) {
      return;
    }
    let newDocTitle = 'Mobility Database';
    if (sortedProviders[0] !== undefined) {
      newDocTitle += ` | ${sortedProviders[0]}`;
    }
    if (feed?.feed_name !== undefined) {
      newDocTitle += ` | ${feed?.feed_name}`;
    }
    document.title = newDocTitle;
    if (
      feed?.data_type === 'gtfs_rt' &&
      feedLoadingStatus === 'loaded' &&
      feed.feed_references !== undefined
    ) {
      dispatch(
        loadingRelatedFeeds({
          feedIds: feed.feed_references,
        }),
      );
    }
    if (
      feedId !== undefined &&
      feed?.data_type === 'gtfs' &&
      feedLoadingStatus === 'loaded'
    ) {
      dispatch(loadingDataset({ feedId }));
    }
    return () => {
      document.title = 'Mobility Database';
    };
  }, [feed, needsToLoadFeed]);

  // The feedId parameter doesn't match the feedId in the store, so we need to load the feed and only render the loading message.
  if (needsToLoadFeed) {
    return wrapComponent(feedLoadingStatus, <span>{t('common:loading')}</span>);
  }
  const hasDatasets = datasets !== undefined && datasets.length > 0;
  const hasFeedRedirect =
    feed?.redirects !== undefined && feed?.redirects.length > 0;
  const downloadLatestUrl =
    feed?.data_type === 'gtfs'
      ? feed?.latest_dataset?.hosted_url
      : feed?.source_info?.producer_url;

  return wrapComponent(
    feedLoadingStatus,
    <Grid container spacing={2}>
      <Grid container item xs={12} spacing={3} alignItems={'center'}>
        <Grid
          item
          sx={{
            cursor: 'pointer',
          }}
          onClick={() => {
            if (history.length === 1) {
              window.location.href = '/feeds';
            } else {
              history.back();
            }
          }}
        >
          <Grid container alignItems={'center'}>
            <ChevronLeft fontSize='small' sx={{ ml: '-20px' }} />{' '}
            <Typography>{t('common:back')}</Typography>
          </Grid>
        </Grid>
        <Grid item>
          <Typography
            sx={{
              a: {
                textDecoration: 'none',
              },
            }}
          >
            <a href='/feeds'>{t('common:feeds')}</a> /{' '}
            <a href={`/feeds?${feed?.data_type}=true`}>
              {feed?.data_type === 'gtfs'
                ? t('common:gtfsSchedule')
                : t('common:gtfsRealtime')}
            </a>{' '}
            / {feed?.id}
          </Typography>
        </Grid>
      </Grid>
      <Grid item xs={12}>
        {getFeedTitleElement(sortedProviders, feed, t)}
      </Grid>
      {feed !== undefined &&
        feed.feed_name !== '' &&
        feed?.data_type === 'gtfs' && (
          <Grid item xs={12}>
            <Typography
              sx={{
                fontWeight: 'bold',
                fontSize: { xs: 18, sm: 24 },
              }}
              data-testid='feed-name'
            >
              {feed?.feed_name}
            </Typography>
          </Grid>
        )}
      {latestDataset?.downloaded_at !== undefined && (
        <Grid item xs={12}>
          <Typography data-testid='last-updated'>
            {`Last updated on ${new Date(
              latestDataset.downloaded_at,
            ).toDateString()}`}
          </Typography>
        </Grid>
      )}
      {feed?.data_type === 'gtfs_rt' && feed.entity_types !== undefined && (
        <Grid item xs={12}>
          <Typography variant='h5'>
            {' '}
            {feed.entity_types
              .map(
                (entityType) =>
                  ({
                    tu: t('common:gtfsRealtimeEntities.tripUpdates'),
                    vp: t('common:gtfsRealtimeEntities.vehiclePositions'),
                    sa: t('common:gtfsRealtimeEntities.serviceAlerts'),
                  })[entityType],
              )
              .join(' ' + t('common:and') + ' ')}
          </Typography>
        </Grid>
      )}
      {feedType === 'gtfs' &&
        datasetLoadingStatus === 'loaded' &&
        !hasDatasets &&
        !hasFeedRedirect && (
          <Grid item xs={12}>
            <WarningContentBox>
              <Trans i18nKey='unableToDownloadFeed'>
                Unable to download this feed. If there is a more recent URL for
                this feed, <a href='/contribute'>please submit it here</a>
              </Trans>
            </WarningContentBox>
          </Grid>
        )}
      {hasFeedRedirect && (
        <Grid item xs={12}>
          <WarningContentBox>
            <Trans i18nKey='feedHasBeenReplaced'>
              This feed has been replaced with a different producer URL.{' '}
              <a href={`/feeds/${feed?.redirects?.[0]?.target_id}`}>
                Go to the new feed here
              </a>
              .
            </Trans>
          </WarningContentBox>
        </Grid>
      )}
      <Grid item xs={12} marginBottom={2}>
        {feedType === 'gtfs' && downloadLatestUrl !== undefined && (
          <Button
            disableElevation
            variant='contained'
            sx={{ marginRight: 2, my: 1 }}
          >
            <a
              href={downloadLatestUrl}
              target='_blank'
              className='btn-link'
              rel='noreferrer'
              id='download-latest-button'
            >
              {t('downloadLatest')}
            </a>
          </Button>
        )}
        {feed?.source_info?.license_url !== undefined &&
          feed?.source_info?.license_url !== '' && (
            <Button
              disableElevation
              variant='contained'
              sx={{ marginRight: 2 }}
            >
              <a
                href={feed?.source_info?.license_url}
                target='_blank'
                className='btn-link'
                rel='noreferrer'
              >
                {t('seeLicense')}
              </a>
            </Button>
          )}
      </Grid>
      <Grid item xs={12}>
        <Grid item xs={12} container rowSpacing={2}>
          <Grid
            container
            direction={{
              xs: feed?.data_type === 'gtfs' ? 'column-reverse' : 'column',
              md: 'row',
            }}
            sx={{ gap: '10px' }}
            justifyContent={'space-between'}
          >
            {feed?.data_type === 'gtfs' && (
              <ContentBox
                title={t('boundingBoxTitle')}
                width={{ xs: '100%', md: '42%' }}
                outlineColor={colors.blue[900]}
                padding={2}
              >
                {boundingBox === undefined && (
                  <WarningContentBox>
                    {t('unableToGenerateBoundingBox')}
                  </WarningContentBox>
                )}
                {boundingBox !== undefined && (
                  <Box width={{ xs: '100%' }} sx={{ mt: 2, mb: 2 }}>
                    <Map polygon={boundingBox} />
                  </Box>
                )}
                <DataQualitySummary latestDataset={latestDataset} />
              </ContentBox>
            )}
            <FeedSummary
              feed={feed}
              sortedProviders={sortedProviders}
              latestDataset={latestDataset}
              width={{ xs: '100%', md: '55%' }}
            />

            {feed?.data_type === 'gtfs_rt' && relatedFeeds !== undefined && (
              <AssociatedFeeds
                feeds={relatedFeeds.filter((f) => f?.id !== feed.id)}
                gtfsRtFeeds={relatedGtfsRtFeeds.filter(
                  (f) => f?.id !== feed.id,
                )}
              />
            )}
          </Grid>
        </Grid>
      </Grid>
      {feed?.data_type === 'gtfs' && hasDatasets && (
        <Grid item xs={12}>
          <PreviousDatasets datasets={datasets} />
        </Grid>
      )}
    </Grid>,
  );
}
