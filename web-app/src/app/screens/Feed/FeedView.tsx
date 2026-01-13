import { Box, Container, CssBaseline, Grid, Typography } from '@mui/material';

// Components
import FeedTitle from './components/FeedTitle';
import OfficialChip from '../../components/OfficialChip';
import DataQualitySummary from './components/DataQualitySummary';
import CoveredAreaMap from '../../components/CoveredAreaMap';
import { Map } from '../../components/Map';
import FeedSummary from './components/FeedSummary';
import AssociatedFeeds from './components/AssociatedFeeds';
import GbfsVersions from './components/GbfsVersions';
import PreviousDatasets from './components/PreviousDatasets';
import { WarningContentBox } from '../../components/WarningContentBox';
import FeedNavigationControls from './components/FeedNavigationControls';

import { getTranslations } from 'next-intl/server';

// Styles
import {
  ctaContainerStyle,
  feedDetailContentContainerStyle,
} from './Feed.styles';

// Utils
import {
  BasicFeedType,
  type GBFSFeedType,
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';
import ClientDownloadButton from './components/ClientDownloadButton';
import { type LatLngExpression } from 'leaflet';
import { type components } from '../../services/feeds/types';
import ClientQualityReportButton from './components/ClientQualityReportButton';

type Props = {
  feed: BasicFeedType;
  feedDataType: string;
  initialDatasets?: components['schemas']['GtfsDataset'][];
  relatedFeeds?: GTFSFeedType[];
  relatedGtfsRtFeeds?: GTFSRTFeedType[];
  totalRoutes?: number;
  routeTypes?: string[];
};

export default async function FeedView({
  feed,
  feedDataType,
  initialDatasets,
  relatedFeeds = [],
  relatedGtfsRtFeeds = [],
  totalRoutes,
  routeTypes,
}: Props) {
  const t = await getTranslations('feeds');
  if (feed == undefined) return <Box>Feed not found</Box>;

  // Basic derived data
  const sortedProviders = feed.provider
    ? String(feed.provider)
        .split(',')
        .map((s) => s.trim())
        .sort()
    : [];

  const downloadLatestUrl =
    feed?.data_type === 'gtfs'
      ? (feed as GTFSFeedType)?.latest_dataset?.hosted_url
      : feed?.source_info?.producer_url;

  console.log('FdownloadLatestUrled:', downloadLatestUrl);

  const hasFeedRedirect = feed?.redirects && feed.redirects.length > 0;

  // Note: Some complex logic from the original FeedClient (like loading additional datasets on mount)
  // is skipped here in favor of Server Rendered initial state.
  // To support "Previous Datasets" fully, we might need a Client Component that takes the initial list
  // and allows fetching more, OR fetch them all on server (pagination support).

  // For now we render the Shell of the view.

  const gbfsAutodiscoveryUrl =
    feed?.data_type === 'gbfs'
      ? (feed as GBFSFeedType)?.source_info?.producer_url
      : undefined; // Simplified

  // Bounding box logic
  // TODO: put it in better place
  const getBoundingBox = (): LatLngExpression[] | undefined => {
    if(feed == undefined ||feed.data_type !== 'gtfs') {
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
      [gtfsFeed.bounding_box.minimum_latitude, gtfsFeed.bounding_box.minimum_longitude],
      [gtfsFeed.bounding_box.minimum_latitude, gtfsFeed.bounding_box.maximum_longitude],
      [gtfsFeed.bounding_box.maximum_latitude, gtfsFeed.bounding_box.maximum_longitude],
      [gtfsFeed.bounding_box.maximum_latitude, gtfsFeed.bounding_box.minimum_longitude],
    ];
  };
  let boundingBox = getBoundingBox();

  // TODO: clean this up
  let latestDataset: components['schemas']['GtfsDataset'] | undefined = undefined;
  if (feed.data_type === 'gtfs') {
    const gtfsFeed: GTFSFeedType = feed;
    latestDataset = initialDatasets?.find(dataset => dataset.id === gtfsFeed.latest_dataset?.id);
  }
  console.log('latest dataset', latestDataset);
  // Derived state for warnings

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
              {/* Attribution Section - extracted simplified */}
              {latestDataset?.validation_report?.validated_at && (
                <Typography variant='caption' component='div'>
                  {`Quality Report Updated: ${new Date(
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

            {/* Warnings */}
            {hasFeedRedirect && (
              <Grid size={12}>
                <WarningContentBox>
                  This feed has been replaced...
                  {/* Use Client Component for interactive warning if needed or just Text */}
                </WarningContentBox>
              </Grid>
            )}

            {/* CTA Buttons */}
            <Box sx={ctaContainerStyle}>
              {feed.data_type === 'gtfs' && downloadLatestUrl && (
                <ClientDownloadButton url={downloadLatestUrl} />
              )}
              {latestDataset?.validation_report?.url_html && (
                <ClientQualityReportButton
                  url={latestDataset.validation_report.url_html}
                />
              )}
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
