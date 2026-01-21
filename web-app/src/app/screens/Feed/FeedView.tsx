// This component is deprecated in favor of FeedView
// They should have the same functionality

import {
  Box,
  Button,
  Container,
  CssBaseline,
  Grid,
  Typography,
} from '@mui/material';

// Components
import FeedTitle from './components/FeedTitle';
import OfficialChip from '../../components/OfficialChip';
import DataQualitySummary from './components/DataQualitySummary';
import CoveredAreaMap from '../../components/CoveredAreaMap';
import FeedSummary from './components/FeedSummary';
import AssociatedFeeds from './components/AssociatedFeeds';
import GbfsVersions from './components/GbfsVersions';
import PreviousDatasets from './components/PreviousDatasets';
import { WarningContentBox } from '../../components/WarningContentBox';
import FeedNavigationControls from './components/FeedNavigationControls';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';

import { getTranslations } from 'next-intl/server';

// Styles
import { ctaContainerStyle } from './Feed.styles';

// Utils
import {
  type BasicFeedType,
  type GBFSFeedType,
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';
import ClientDownloadButton from './components/ClientDownloadButton';
import { type LatLngTuple } from 'leaflet';
import { type components } from '../../services/feeds/types';
import ClientQualityReportButton from './components/ClientQualityReportButton';

interface Props {
  feed: BasicFeedType;
  feedDataType: string;
  initialDatasets?: Array<components['schemas']['GtfsDataset']>;
  relatedFeeds?: GTFSFeedType[];
  relatedGtfsRtFeeds?: GTFSRTFeedType[];
  totalRoutes?: number;
  routeTypes?: string[];
}

export default async function FeedView({
  feed,
  feedDataType,
  initialDatasets,
  relatedFeeds = [],
  relatedGtfsRtFeeds = [],
  totalRoutes,
  routeTypes,
}: Props): Promise<React.ReactElement> {
  const t = await getTranslations('feeds');
  const tGbfs = await getTranslations('gbfs');
  const tCommon = await getTranslations('common');
  if (feed == undefined) return <Box>Feed not found</Box>;

  // Basic derived data
  const sortedProviders =
    feed.provider != null && String(feed.provider).trim().length > 0
      ? String(feed.provider)
          .split(',')
          .map((s) => s.trim())
          .sort()
      : [];

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
        {tGbfs('openAutoDiscoveryUrl')}
      </Button>
    );
  };

  const hasFeedRedirect = feed?.redirects != null && feed.redirects.length > 0;

  const gbfsAutodiscoveryUrl =
    feed?.data_type === 'gbfs'
      ? (feed as GBFSFeedType)?.source_info?.producer_url
      : undefined; // Simplified

  // Bounding box logic
  // TODO: put it in better place
  const getBoundingBox = (): LatLngTuple[] | undefined => {
    if (feed == undefined || feed.data_type !== 'gtfs') {
      return undefined;
    }
    const gtfsFeed: GTFSFeedType = feed;
    if (
      gtfsFeed.bounding_box?.maximum_latitude == undefined ||
      gtfsFeed.bounding_box?.maximum_longitude == undefined ||
      gtfsFeed.bounding_box?.minimum_latitude == undefined ||
      gtfsFeed.bounding_box?.minimum_longitude == undefined
    ) {
      return undefined;
    }
    return [
      [
        gtfsFeed.bounding_box.minimum_latitude,
        gtfsFeed.bounding_box.minimum_longitude,
      ],
      [
        gtfsFeed.bounding_box.minimum_latitude,
        gtfsFeed.bounding_box.maximum_longitude,
      ],
      [
        gtfsFeed.bounding_box.maximum_latitude,
        gtfsFeed.bounding_box.maximum_longitude,
      ],
      [
        gtfsFeed.bounding_box.maximum_latitude,
        gtfsFeed.bounding_box.minimum_longitude,
      ],
    ];
  };
  const boundingBox = getBoundingBox();

  // TODO: clean this up
  let latestDataset: components['schemas']['GtfsDataset'] | undefined;
  if (feed.data_type === 'gtfs') {
    const gtfsFeed: GTFSFeedType = feed;
    latestDataset = initialDatasets?.find(
      (dataset) => dataset.id === gtfsFeed.latest_dataset?.id,
    );
  }

  // Derived state for warnings
  const hasDatasets =
    initialDatasets != undefined && initialDatasets.length > 0;

  return (
    <Container
      component='main'
      sx={{ width: '100%', m: 'auto', px: 0 }}
      maxWidth='xl'
    >
      <CssBaseline />
      <Box sx={{ display: 'flex', flexDirection: 'column' }}>
        <Box
          sx={{
            width: '100%',
            bgcolor: 'background.paper',
            borderRadius: '6px 0px 0px 6px',
            p: 3,
            color: 'text.primary',
            fontSize: '18px',
            fontWeight: 700,
            position: 'relative',
          }}
        >
          <Box sx={{ position: 'relative' }}>
            <FeedNavigationControls
              feedDataType={feed.data_type ?? ''}
              feedId={feed.id ?? ''}
            />

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
                latestDataset={(feed as GTFSFeedType)?.latest_dataset}
              />
            )}

            {feed?.data_type === 'gtfs_rt' && feed.official === true && (
              <Box sx={{ my: 1 }}>
                <OfficialChip></OfficialChip>
              </Box>
            )}

            <Box>
              {latestDataset?.validation_report?.validated_at != null && (
                <Typography
                  data-testid='last-updated'
                  variant='caption'
                  width={'100%'}
                  component='div'
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
              {feed.external_ids?.some((eId) => eId.source === 'tld') ===
                true && (
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
              {feed.external_ids?.some((eId) => eId.source === 'ntd') ===
                true && (
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
                          (
                            ({
                              tu: tCommon('gtfsRealtimeEntities.tripUpdates'),
                              vp: tCommon(
                                'gtfsRealtimeEntities.vehiclePositions',
                              ),
                              sa: tCommon('gtfsRealtimeEntities.serviceAlerts'),
                            }) as const satisfies Record<string, string>
                          )[entityType],
                      )
                      .join(` ${tCommon('and')} `)}
                  </Typography>
                </Grid>
              )}

            {/* Warnings */}
            {feedDataType === 'gtfs' && !hasDatasets && !hasFeedRedirect && (
              <WarningContentBox>
                {t.rich('unableToDownloadFeed', {
                  link: (chunks) => (
                    <Button
                      variant='text'
                      className='inline'
                      href='/contribute'
                    >
                      {chunks}
                    </Button>
                  ),
                })}
              </WarningContentBox>
            )}
            {hasFeedRedirect && (
              <Grid size={12}>
                <WarningContentBox>
                  {t.rich('feedHasBeenReplaced', {
                    link: (chunks) => (
                      <Button
                        variant='text'
                        className='inline'
                        href={`/feeds/${feed?.redirects?.[0]?.target_id}`}
                      >
                        {chunks}
                      </Button>
                    ),
                  })}
                </WarningContentBox>
              </Grid>
            )}

            {/* CTA Buttons */}
            <Box sx={ctaContainerStyle}>
              {feed.data_type === 'gtfs' &&
                downloadLatestUrl != null &&
                downloadLatestUrl.length > 0 && (
                  <ClientDownloadButton url={downloadLatestUrl} />
                )}
              {latestDataset?.validation_report?.url_html != null &&
                latestDataset.validation_report.url_html.length > 0 && (
                  <ClientQualityReportButton
                    url={latestDataset.validation_report.url_html}
                  />
                )}
              {feed?.data_type === 'gbfs' && <>{gbfsOpenFeedUrlElement()}</>}
            </Box>

            <Grid size={12}>
              <Box
                sx={{
                  width: '100%',
                  display: 'flex',
                  flexDirection: {
                    xs:
                      feed.data_type === 'gtfs_rt'
                        ? 'column'
                        : 'column-reverse',
                    md: feed.data_type === 'gtfs_rt' ? 'row' : 'row-reverse',
                  },
                  gap: 2,
                  flexWrap: 'nowrap',
                  justifyContent: 'space-between',
                  mb: 4,
                }}
              >
                {(feed.data_type === 'gtfs' || feed.data_type === 'gbfs') && (
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
                    totalRoutes={totalRoutes}
                    routeTypes={routeTypes}
                  />
                </Box>
                {feed?.data_type === 'gtfs_rt' && (
                  <AssociatedFeeds
                    feeds={relatedFeeds.filter((f) => f?.id !== feed.id)}
                    gtfsRtFeeds={relatedGtfsRtFeeds.filter(
                      (f) => f?.id !== feed.id,
                    )}
                  />
                )}
              </Box>
            </Grid>

            {feed?.data_type === 'gbfs' && (
              <GbfsVersions feed={feed as GBFSFeedType}></GbfsVersions>
            )}

            {feed.data_type === 'gtfs' && (
              <Grid size={12}>
                <PreviousDatasets
                  initialDatasets={initialDatasets}
                  feedId={feed.id ?? ''}
                />
              </Grid>
            )}
          </Box>
        </Box>
      </Box>
    </Container>
  );
}
