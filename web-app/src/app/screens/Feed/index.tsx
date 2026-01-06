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
import { loadingFeed, loadingRelatedFeeds } from '../../store/feed-reducer';
import {
  selectIsAnonymous,
  selectIsAuthenticated,
  selectUserProfile,
} from '../../store/profile-selectors';
import {
  selectFeedData,
  selectFeedLoadingStatus,
  selectRelatedFeedsData,
  selectRelatedGtfsRTFeedsData,
  selectAutoDiscoveryUrl,
  selectFeedBoundingBox,
} from '../../store/feed-selectors';
import { clearDataset, loadingDataset } from '../../store/dataset-reducer';
import {
  selectDatasetsData,
  selectDatasetsLoadingStatus,
  selectHasLoadedAllDatasets,
  selectLatestDatasetsData,
} from '../../store/dataset-selectors';
import PreviousDatasets from './components/PreviousDatasets';
import DataQualitySummary from './components/DataQualitySummary';
import AssociatedFeeds from './components/AssociatedFeeds';
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
import FeedTitle from './components/FeedTitle';
import OfficialChip from '../../components/OfficialChip';
import {
  type GBFSFeedType,
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';
import DownloadIcon from '@mui/icons-material/Download';
import GbfsVersions from './components/GbfsVersions';
import generateFeedStructuredData from './StructuredData.functions';
import ReactGA from 'react-ga4';
import FeedSummary from './components/FeedSummary';

const wrapComponent = (
  feedLoadingStatus: string,
  descriptionMeta: string | undefined,
  feedDataType: string | undefined,
  feedId: string | undefined,
  structuredData: Record<string, unknown> | undefined,
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
              window.location.origin + '/feeds/' + feedDataType + '/' + feedId
            }
          />
        )}
        {structuredData != undefined && (
          <script type='application/ld+json'>
            {JSON.stringify(structuredData)}
          </script>
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
            position: 'relative',
          }}
        >
          {feedLoadingStatus === 'error' && <>{t('errorLoadingFeed')}</>}
          {feedLoadingStatus !== 'error' ? child : null}
        </Box>
      </Box>
    </Container>
  );
};

const handleDownloadLatestClick = (): void => {
  ReactGA.event({
    category: 'engagement',
    action: 'download_latest_dataset',
    label: 'Download Latest Dataset',
  });
};

const handleOpenFullQualityReportClick = (): void => {
  ReactGA.event({
    category: 'engagement',
    action: 'open_full_quality_report',
    label: 'Open Full Quality Report',
  });
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
  const boundingBox = useSelector(selectFeedBoundingBox);
  const feed = useSelector(selectFeedData);
  const gbfsAutodiscoveryUrl = useSelector(selectAutoDiscoveryUrl);
  const needsToLoadFeed = feed === undefined || feed?.id !== feedId;
  const isAuthenticatedOrAnonymous =
    useSelector(selectIsAuthenticated) || useSelector(selectIsAnonymous);
  const sortedProviders = formatProvidersSorted(feed?.provider ?? '');
  const DATASET_CALL_LIMIT = 10;
  const [structuredData, setStructuredData] = React.useState<
    Record<string, unknown> | undefined
  >();

  React.useMemo(() => {
    const structuredData = generateFeedStructuredData(
      feed,
      generateDescriptionMetaTag(
        t,
        sortedProviders,
        feed?.data_type,
        feed?.feed_name,
      ),
      relatedFeeds,
      relatedGtfsRtFeeds,
    );
    setStructuredData(structuredData);
  }, [feed, relatedFeeds, relatedGtfsRtFeeds]);

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
    if (
      feed?.data_type === 'gtfs_rt' &&
      feedLoadingStatus === 'loaded' &&
      (feed as GTFSRTFeedType)?.feed_references != undefined
    ) {
      dispatch(
        loadingRelatedFeeds({
          feedIds: (feed as GTFSRTFeedType)?.feed_references ?? [],
        }),
      );
    }
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
      structuredData,
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
            gap: 2,
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
  const downloadLatestUrl =
    feed?.data_type === 'gtfs'
      ? (feed as GTFSFeedType)?.latest_dataset?.hosted_url
      : feed?.source_info?.producer_url;

  const gbfsOpenFeedUrlElement = (): React.JSX.Element => {
    if (gbfsAutodiscoveryUrl == undefined) {
      return <></>;
    }
    return (
      <Button
        disableElevation
        variant='contained'
        sx={{ marginRight: 2 }}
        href={gbfsAutodiscoveryUrl}
        target='_blank'
        rel='noreferrer'
        endIcon={<OpenInNewIcon></OpenInNewIcon>}
      >
        {t('gbfs:openAutoDiscoveryUrl')}
      </Button>
    );
  };

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
    structuredData,
    <Box sx={{ position: 'relative' }}>
      <Grid container size={12} spacing={3} alignItems={'end'}>
        <Button
          sx={{ py: 0 }}
          size='large'
          startIcon={<ChevronLeft />}
          color={'inherit'}
          onClick={() => {
            if (history.length === 1) {
              window.location.href = '/feeds';
            } else {
              history.back();
            }
          }}
        >
          {t('common:back')}
        </Button>

        <Grid>
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
              {t(`common:${feed?.data_type}`)}
            </Button>
            /{' '}
            {feed.data_type === 'gbfs'
              ? feed?.id?.replace('gbfs-', '')
              : feed?.id}
          </Typography>
        </Grid>
      </Grid>
      <Box sx={{ mt: 2 }}>
        <FeedTitle sortedProviders={sortedProviders} feed={feed} />
      </Box>
      {feed?.feed_name !== '' && feed?.data_type === 'gtfs' && (
        <Grid size={12}>
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
        {feed.external_ids?.some((eId) => eId.source === 'tld') === true && (
          <Typography
            data-testid='transitland-attribution'
            variant={'caption'}
            width={'100%'}
            component={'div'}
          >
            {t('dataAttribution')}{' '}
            <a
              rel='noreferrer nofollow'
              target='_blank'
              href='https://www.transit.land/terms'
            >
              Transitland
            </a>
          </Typography>
        )}
        {feed.external_ids?.some((eId) => eId.source === 'ntd') === true && (
          <Typography
            data-testid='fta-attribution'
            variant={'caption'}
            width={'100%'}
            component={'div'}
          >
            {t('dataAttribution')}
            {' the United States '}
            <a
              rel='noreferrer nofollow'
              target='_blank'
              href='https://www.transit.dot.gov/ntd/data-product/2023-annual-database-general-transit-feed-specification-gtfs-weblinks'
            >
              National Transit Database
            </a>
          </Typography>
        )}
      </Box>

      {feed?.data_type === 'gtfs_rt' &&
        (feed as GTFSRTFeedType)?.entity_types != undefined && (
          <Grid size={12}>
            <Typography variant='h5'>
              {' '}
              {((feed as GTFSRTFeedType)?.entity_types ?? [])
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
          <WarningContentBox>
            <Trans i18nKey='unableToDownloadFeed'>
              Unable to download this feed. If there is a more recent URL for
              this feed,{' '}
              <Button variant='text' className='inline' href='/contribute'>
                please submit it here
              </Button>
            </Trans>
          </WarningContentBox>
        )}
      {hasFeedRedirect && (
        <Grid size={12}>
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
        {feedType === 'gtfs' && downloadLatestUrl != undefined && (
          <Button
            disableElevation
            variant='contained'
            href={downloadLatestUrl}
            target='_blank'
            rel='noreferrer nofollow'
            id='download-latest-button'
            endIcon={<DownloadIcon></DownloadIcon>}
            onClick={handleDownloadLatestClick}
          >
            {t('downloadLatest')}
          </Button>
        )}
        {latestDataset?.validation_report?.url_html != undefined && (
          <Button
            variant='outlined'
            disableElevation
            href={`${latestDataset?.validation_report?.url_html}`}
            target='_blank'
            rel='noreferrer nofollow'
            endIcon={<OpenInNewIcon></OpenInNewIcon>}
            onClick={handleOpenFullQualityReportClick}
          >
            {t('openFullQualityReport')}
          </Button>
        )}
        {feed?.data_type === 'gbfs' && <>{gbfsOpenFeedUrlElement()}</>}
      </Box>
      <Grid size={12}>
        <Box
          sx={feedDetailContentContainerStyle({
            isGtfsRT: feed?.data_type === 'gtfs_rt',
          })}
        >
          {(feed?.data_type === 'gtfs' || feed.data_type === 'gbfs') && (
            <CoveredAreaMap
              boundingBox={boundingBox}
              latestDataset={latestDataset}
              feed={feed}
            />
          )}

          <Box sx={{ width: { xs: '100%', md: '475px' } }}>
            <FeedSummary
              feed={feed}
              sortedProviders={sortedProviders}
              latestDataset={latestDataset}
              autoDiscoveryUrl={gbfsAutodiscoveryUrl}
            />
          </Box>

          {feed?.data_type === 'gtfs_rt' && relatedFeeds != undefined && (
            <AssociatedFeeds
              feeds={relatedFeeds.filter((f) => f?.id !== feed.id)}
              gtfsRtFeeds={relatedGtfsRtFeeds.filter((f) => f?.id !== feed.id)}
            />
          )}
        </Box>
      </Grid>

      {feed?.data_type === 'gbfs' && (
        <GbfsVersions feed={feed as GBFSFeedType}></GbfsVersions>
      )}

      {feed?.data_type === 'gtfs' && hasDatasets && (
        <Grid size={12}>
          <PreviousDatasets
            datasets={datasets}
            isLoadingDatasets={datasetLoadingStatus === 'loading'}
            hasloadedAllDatasets={hasLoadedAllDatasets ?? false}
            loadMoreDatasets={(offset: number) => {
              loadDatasets(offset);
            }}
          />
        </Grid>
      )}
    </Box>,
  );
}
