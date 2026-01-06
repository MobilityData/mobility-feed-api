
import { Box, Container, CssBaseline, Grid, Typography } from '@mui/material';

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

// Styles
import {
  ctaContainerStyle,
  feedDetailContentContainerStyle,
} from './Feed.styles';

// Utils
import {
  type GBFSFeedType,
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';
import ClientDownloadButton from './components/ClientDownloadButton';

type Props = {
  feed: any; // Using explicit type would be better, but 'any' allows quick porting of varied feed types
  feedDataType: string;
  // We can also pass other preloaded data here if fetched in page.tsx
};

export default function FeedView({ feed, feedDataType }: Props) {
  if (!feed) return <Box>Feed not found</Box>;

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
  let boundingBox = undefined;
  if (feed.latest_dataset?.bounding_box) {
    boundingBox = feed.latest_dataset.bounding_box;
  }

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
              feedDataType={feed.data_type}
              feedId={feed.id}
            />

            <Box sx={{ mt: 2 }}>
              {/* FeedTitle internally might use useTranslation, ensure it is Client or handles it */}
              {/* If FeedTitle is just UI, it's fine. */}
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
                latestDataset={feed.latest_dataset}
              />
            )}

            {feed?.data_type === 'gtfs_rt' && feed.official === true && (
              <Box sx={{ my: 1 }}>
                <OfficialChip></OfficialChip>
              </Box>
            )}

            <Box>
              {/* Attribution Section - extracted simplified */}
              {feed.latest_dataset?.validation_report?.validated_at && (
                <Typography variant='caption' component='div'>
                  {`Quality Report Updated: ${new Date(
                    feed.latest_dataset.validation_report.validated_at,
                  ).toDateString()}`}
                </Typography>
              )}
              {/* ... Add other attributions ... */}
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
              {feed.latest_dataset?.validation_report?.url_html && (
                <ClientDownloadButton
                  url={feed.latest_dataset.validation_report.url_html}
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
                    latestDataset={feed.latest_dataset}
                    feed={feed}
                  />
                )}
                <Box sx={{ width: { xs: '100%', md: '475px' } }}>
                  <FeedSummary
                    feed={feed}
                    sortedProviders={sortedProviders}
                    latestDataset={feed.latest_dataset}
                    autoDiscoveryUrl={gbfsAutodiscoveryUrl}
                  />
                </Box>
                {feed?.data_type === 'gtfs_rt' && (
                  /* Associated feeds need to be fetched or passed. 
                                In FeedClient it was fetching `relatedFeeds`.
                                We strictly should fetch them in page.tsx and pass as props. 
                                For now we skip or can pass empty list. */
                  <AssociatedFeeds feeds={[]} gtfsRtFeeds={[]} />
                )}
              </Box>
            </Grid>

            {feed?.data_type === 'gbfs' && (
              <GbfsVersions feed={feed as GBFSFeedType}></GbfsVersions>
            )}

            {/* Previous Datasets */}
            {/* This requires fetching datasets. page.tsx should fetch initial list. */}
            {feed.data_type === 'gtfs' && (
              <Grid size={12}>
                {/* <PreviousDatasets ... /> - Needs client logic or pre-fetched data props */}
                <Typography>Previous Datasets (Server Placeholder)</Typography>
              </Grid>
            )}
          </Box>
        </Box>
      </Box>
    </Container>
  );
}
