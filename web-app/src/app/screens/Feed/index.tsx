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
  Skeleton,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { ChevronLeft } from '@mui/icons-material';

import { useAppDispatch } from '../../hooks';
import { loadingFeed } from '../../store/feed-reducer';
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
  selectHasLoadedAllDatasets,
  selectLatestDatasetsData,
} from '../../store/dataset-selectors';
import PreviousDatasets from './PreviousDatasets';
import FeedSummary from './FeedSummary';
import DataQualitySummary from './DataQualitySummary';
import AssociatedFeeds from './AssociatedFeeds';
import { WarningContentBox } from '../../components/WarningContentBox';
import { Trans, useTranslation } from 'react-i18next';
import { Helmet } from 'react-helmet-async';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import {
  ctaContainerStyle,
  feedDetailContentContainerStyle,
} from './Feed.styles';
import CoveredAreaMap from '../../components/CoveredAreaMap';

import {
  formatProvidersSorted,
  generatePageTitle,
  generateDescriptionMetaTag,
} from './Feed.functions';
import FeedTitle from './FeedTitle';
import OfficialChip from '../../components/OfficialChip';

const wrapComponent = (
  feedLoadingStatus: string,
  descriptionMeta: string | undefined,
  feedDataType: string | undefined,
  feedId: string | undefined,
  child: React.ReactElement,
): React.ReactElement => {
  const { t } = useTranslation('feeds');
  const theme = useTheme();
  return (
    <Container
      component='main'
      sx={{ width: '100%', m: 'auto', px: 0 }}
      maxWidth='xl'
    >
      <Helmet>
        {descriptionMeta != undefined && (
          <meta name='description' content={descriptionMeta} />
        )}
        {feedDataType != undefined && (
          <link
            rel='canonical'
            href={
              window.location.origin + 'feeds/' + feedDataType + '/' + feedId
            }
          />
        )}
      </Helmet>

      <CssBaseline />
      <Box sx={{ display: 'flex', flexDirection: 'column' }}>
        <Box
          sx={{
            width: '100%',
            background: theme.palette.background.paper,
            borderRadius: '6px 0px 0px 6px',
            p: 3,
            color: theme.palette.text.primary,
            fontSize: '18px',
            fontWeight: 700,
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
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const { feedId, feedDataType } = useParams();
  const user = useSelector(selectUserProfile);
  const feedLoadingStatus = useSelector(selectFeedLoadingStatus);
  const datasetLoadingStatus = useSelector(selectDatasetsLoadingStatus);
  const dataTypeSelector = useSelector(selectFeedData)?.data_type;
  const feedType = feedDataType ?? dataTypeSelector;
  const relatedFeeds = useSelector(selectRelatedFeedsData);
  const relatedGtfsRtFeeds = useSelector(selectRelatedGtfsRTFeedsData);
  const datasets = useSelector(selectDatasetsData);
  const hasLoadedAllDatasets = useSelector(selectHasLoadedAllDatasets);
  const latestDataset = useSelector(selectLatestDatasetsData);
  const boundingBox = useSelector(selectBoundingBoxFromLatestDataset);
  const gtfsFeedData = useSelector(selectGTFSFeedData);
  const gtfsRtFeedData = useSelector(selectGTFSRTFeedData);
  const feed = feedType === 'gtfs' ? gtfsFeedData : gtfsRtFeedData;
  const needsToLoadFeed = feed === undefined || feed?.id !== feedId;
  const isAuthenticatedOrAnonymous =
    useSelector(selectIsAuthenticated) || useSelector(selectIsAnonymous);
  const sortedProviders = formatProvidersSorted(feed?.provider ?? '');
  const DATASET_CALL_LIMIT = 10;

  const loadDatasets = (offset: number): void => {
    if (feedId != undefined && hasLoadedAllDatasets === false) {
      dispatch(
        loadingDataset({
          feedId,
          offset,
          limit: DATASET_CALL_LIMIT,
        }),
      );
    }
  };

  useEffect(() => {
    if (user != undefined && feedId != undefined && needsToLoadFeed) {
      dispatch(clearDataset());
      dispatch(loadingFeed({ feedId, feedDataType }));
      if (feedDataType === 'gtfs') {
        loadDatasets(0);
      }
    }
  }, [isAuthenticatedOrAnonymous, needsToLoadFeed]);

  useEffect(() => {
    if (needsToLoadFeed) {
      return;
    }
    document.title = generatePageTitle(
      sortedProviders,
      feed.data_type,
      feed?.feed_name,
    );
    // if (
    //   feed?.data_type === 'gtfs_rt' &&
    //   feedLoadingStatus === 'loaded' &&
    //   // feed.feed_references != undefined
    // ) {
    //   dispatch(
    //     loadingRelatedFeeds({
    //       feedIds: feed.feed_references,
    //     }),
    //   );
    // }
    if (
      feedId != undefined &&
      feed?.data_type === 'gtfs' &&
      feedLoadingStatus === 'loaded' &&
      datasets == undefined
    ) {
      loadDatasets(0);
    }
    return () => {
      document.title = 'Mobility Database';
    };
  }, [feed, needsToLoadFeed]);

  // The feedId parameter doesn't match the feedId in the store, so we need to load the feed and only render the loading message.
  const areDatasetsLoading =
    feed?.data_type === 'gtfs' &&
    datasetLoadingStatus === 'loading' &&
    datasets == undefined;
  const isCurrenltyLoadingFeed =
    feedLoadingStatus === 'loading' || areDatasetsLoading;
  if (needsToLoadFeed || isCurrenltyLoadingFeed) {
    return wrapComponent(
      feedLoadingStatus,
      undefined,
      feedType,
      feedId,
      <Box>
        <Skeleton
          animation='wave'
          variant='text'
          sx={{ fontSize: '2rem', width: '300px' }}
        />
        <Skeleton
          animation='wave'
          variant='text'
          sx={{ fontSize: '3rem', width: { xs: '100%', sm: '500px' } }}
        />
        <Skeleton
          animation='wave'
          variant='rounded'
          height={'30px'}
          width={'300px'}
        />
        <Box
          sx={{
            background: 'rgba(0,0,0,0.2)',
            height: '1px',
            width: '100%',
            mb: 3,
            mt: 2,
          }}
        ></Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Skeleton
            animation='wave'
            variant='rectangular'
            width={'162px'}
            height={'40px'}
          />
          <Skeleton
            animation='wave'
            variant='rectangular'
            width={'162px'}
            height={'40px'}
          />
        </Box>
        <Box
          sx={{
            mt: 2,
            display: 'flex',
            justifyContent: 'space-between',
            gap: 3,
            flexWrap: { xs: 'wrap', sm: 'nowrap' },
          }}
        >
          <Skeleton
            animation='wave'
            variant='rectangular'
            sx={{ width: { xs: '100%', sm: '100%' }, height: '630px' }}
          />
          <Skeleton
            animation='wave'
            variant='rectangular'
            sx={{
              width: { xs: '100%', sm: '100%' },
              height: '630px',
            }}
          />
        </Box>
      </Box>,
    );
  }
  const hasDatasets = datasets != undefined && datasets.length > 0;
  const hasFeedRedirect =
    feed?.redirects != undefined && feed?.redirects.length > 0;
  // const downloadLatestUrl =
  //   feed?.data_type === 'gtfs'
  //     ? feed?.latest_dataset?.hosted_url
  //     : feed?.source_info?.producer_url;

  return wrapComponent(
    feedLoadingStatus,
    generateDescriptionMetaTag(
      t,
      sortedProviders,
      feed.data_type,
      feed?.feed_name,
    ),
    feedType,
    feedId,
    <Box>
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
            <Button variant='text' href='/feeds' className='inline'>
              {t('common:feeds')}
            </Button>
            /
            <Button
              variant='text'
              href={`/feeds?${feed?.data_type}=true`}
              className='inline'
            >
              {feed?.data_type === 'gtfs'
                ? t('common:gtfsSchedule')
                : t('common:gtfsRealtime')}
            </Button>
            / {feed?.id}
          </Typography>
        </Grid>
      </Grid>
      <Box sx={{ mt: 2 }}>
        <FeedTitle sortedProviders={sortedProviders} feed={feed} />
      </Box>
      {feed?.feed_name !== '' && feed?.data_type === 'gtfs' && (
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

      {feed?.data_type === 'gtfs' && (
        <DataQualitySummary
          feedStatus={feed?.status}
          isOfficialFeed={feed.official === true}
          latestDataset={latestDataset}
        />
      )}
      {feed?.data_type === 'gtfs_rt' && feed.official === true && (
        <Box sx={{ my: 1 }}>
          <OfficialChip></OfficialChip>
        </Box>
      )}
      <Box>
        {latestDataset?.validation_report?.validated_at != undefined && (
          <Typography
            data-testid='last-updated'
            variant={'caption'}
            width={'100%'}
            component={'div'}
          >
            {`${t('qualityReportUpdated')}: ${new Date(
              latestDataset.validation_report.validated_at,
            ).toDateString()}`}
          </Typography>
        )}
        {feed?.official_updated_at != undefined && (
          <Typography
            data-testid='last-updated'
            variant={'caption'}
            width={'100%'}
            component={'div'}
          >
            {`${t('officialFeedUpdated')}: ${new Date(
              feed?.official_updated_at,
            ).toDateString()}`}
          </Typography>
        )}
      </Box>

      {/* {feed?.data_type === 'gtfs_rt' && feed.entity_types != undefined && ( */}
      {/*  <Grid item xs={12}> */}
      {/*    <Typography variant='h5'> */}
      {/*      {' '} */}
      {/*      {feed.entity_types */}
      {/*        .map( */}
      {/*          (entityType) => */}
      {/*            ({ */}
      {/*              tu: t('common:gtfsRealtimeEntities.tripUpdates'), */}
      {/*              vp: t('common:gtfsRealtimeEntities.vehiclePositions'), */}
      {/*              sa: t('common:gtfsRealtimeEntities.serviceAlerts'), */}
      {/*            })[entityType], */}
      {/*        ) */}
      {/*        .join(' ' + t('common:and') + ' ')} */}
      {/*    </Typography> */}
      {/*  </Grid> */}
      {/* )} */}
      {/* {feedType === 'gtfs' && */}
      {/*  datasetLoadingStatus === 'loaded' && */}
      {/*  !hasDatasets && */}
      {/*  !hasFeedRedirect && ( */}
      {/*    <WarningContentBox> */}
      {/*      <Trans i18nKey='unableToDownloadFeed'> */}
      {/*        Unable to download this feed. If there is a more recent URL for */}
      {/*        this feed,{' '} */}
      {/*        <Button variant='text' className='inline' href='/contribute'> */}
      {/*          please submit it here */}
      {/*        </Button> */}
      {/*      </Trans> */}
      {/*    </WarningContentBox> */}
      {/*  )} */}
      {hasFeedRedirect && (
        <Grid item xs={12}>
          <WarningContentBox>
            <Trans i18nKey='feedHasBeenReplaced'>
              This feed has been replaced with a different producer URL.
              <Button
                variant='text'
                className='inline'
                href={`/feeds/${feed?.redirects?.[0]?.target_id}`}
              >
                Go to the new feed here
              </Button>
            </Trans>
          </WarningContentBox>
        </Grid>
      )}
      <Box sx={ctaContainerStyle}>
        {/* {feedType === 'gtfs' && downloadLatestUrl != undefined && ( */}
        {/*  <Button */}
        {/*    disableElevation */}
        {/*    variant='contained' */}
        {/*    href={downloadLatestUrl} */}
        {/*    target='_blank' */}
        {/*    rel='noreferrer nofollow' */}
        {/*    id='download-latest-button' */}
        {/*    endIcon={<DownloadIcon></DownloadIcon>} */}
        {/*  > */}
        {/*    {t('downloadLatest')} */}
        {/*  </Button> */}
        {/* )} */}
        {/* {latestDataset?.validation_report?.url_html != undefined && ( */}
        {/*  <Button */}
        {/*    variant='contained' */}
        {/*    disableElevation */}
        {/*    href={`${latestDataset?.validation_report?.url_html}`} */}
        {/*    target='_blank' */}
        {/*    rel='noreferrer nofollow' */}
        {/*    endIcon={<OpenInNewIcon></OpenInNewIcon>} */}
        {/*  > */}
        {/*    {t('openFullQualityReport')} */}
        {/*  </Button> */}
        {/* )} */}
        {feed?.source_info?.license_url != undefined &&
          feed?.source_info?.license_url !== '' && (
            <Button
              disableElevation
              variant='contained'
              sx={{ marginRight: 2 }}
              href={feed?.source_info?.license_url}
              target='_blank'
              rel='noreferrer'
              endIcon={<OpenInNewIcon></OpenInNewIcon>}
            >
              {t('seeLicense')}
            </Button>
          )}
      </Box>
      <Grid item xs={12}>
        <Box
          sx={feedDetailContentContainerStyle({
            theme,
            isGtfsSchedule: feed?.data_type === 'gtfs',
          })}
        >
          {feed?.data_type === 'gtfs' && (
            <CoveredAreaMap
              boundingBox={boundingBox}
              latestDataset={latestDataset}
            />
          )}
          <FeedSummary
            feed={feed}
            sortedProviders={sortedProviders}
            latestDataset={latestDataset}
            width={{ xs: '100%' }}
          />

          {feed?.data_type === 'gtfs_rt' && relatedFeeds != undefined && (
            <AssociatedFeeds
              feeds={relatedFeeds.filter((f) => f?.id !== feed.id)}
              gtfsRtFeeds={relatedGtfsRtFeeds.filter((f) => f?.id !== feed.id)}
            />
          )}
        </Box>
      </Grid>
      {feed?.data_type === 'gtfs' && hasDatasets && (
        <Grid item xs={12}>
          <PreviousDatasets
            datasets={datasets}
            isLoadingDatasets={datasetLoadingStatus === 'loading'}
            hasloadedAllDatasets={
              hasLoadedAllDatasets != undefined && hasLoadedAllDatasets
            }
            loadMoreDatasets={(offset: number) => {
              loadDatasets(offset);
            }}
          />
        </Grid>
      )}
    </Box>,
  );
}
