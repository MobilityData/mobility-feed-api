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
import {
  ChevronLeft,
  Download,
  LaunchOutlined,
  WarningAmberOutlined,
} from '@mui/icons-material';
import '../../styles/SignUp.css';
import '../../styles/FAQ.css';
import { ContentBox } from '../../components/ContentBox';
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
} from '../../store/feed-selectors';
import { loadingDataset } from '../../store/dataset-reducer';
import {
  selectBoundingBoxFromLatestDataset,
  selectDatasetsData,
  selectLatestDatasetsData,
} from '../../store/dataset-selectors';
import { Map } from '../../components/Map';
import PreviousDatasets from './PreviousDatasets';
import AssociatedGTFSRTFeeds from './AssociatedGTFSRTFeeds';
import FeedSummary from './FeedSummary';
import DataQualitySummary from './DataQualitySummary';

export default function Feed(): React.ReactElement {
  const { feedId } = useParams();
  const user = useSelector(selectUserProfile);
  const feedLoadingStatus = useSelector(selectFeedLoadingStatus);
  const feedType = useSelector(selectFeedData)?.data_type;
  const feed =
    feedType === 'gtfs'
      ? useSelector(selectGTFSFeedData)
      : useSelector(selectGTFSRTFeedData);
  const datasets = useSelector(selectDatasetsData);
  const latestDataset = useSelector(selectLatestDatasetsData);
  const boundingBox = useSelector(selectBoundingBoxFromLatestDataset);
  const dispatch = useAppDispatch();
  const isAuthenticatedOrAnonymous =
    useSelector(selectIsAuthenticated) || useSelector(selectIsAnonymous);

  useEffect(() => {
    if (
      isAuthenticatedOrAnonymous &&
      user?.accessToken !== undefined &&
      feedId !== undefined
    ) {
      dispatch(loadingFeed({ feedId, accessToken: user?.accessToken }));
      dispatch(loadingDataset({ feedId, accessToken: user?.accessToken }));
    }
  }, [isAuthenticatedOrAnonymous]);

  return (
    <Container component='main' sx={{ width: '100vw', m: 0 }}>
      <CssBaseline />
      <Box
        sx={{ mt: 12, display: 'flex', flexDirection: 'column', m: 10 }}
        margin={{ xs: '20px', sm: '80px' }}
      >
        <Box
          sx={{
            width: '90vw',
            background: '#F8F5F5',
            borderRadius: '6px 0px 0px 6px',
            p: 5,
            color: 'black',
            fontSize: '18px',
            fontWeight: 700,
            mr: 0,
          }}
        >
          {feedLoadingStatus === 'error' && (
            <>There was an error loading the feed.</>
          )}
          {feedLoadingStatus === 'loading' && 'Loading...'}
          {feedLoadingStatus === 'loaded' && (
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
                    <ChevronLeft /> Back
                  </Grid>
                </Grid>
                <Grid item>
                  <Typography>
                    Feeds /{' '}
                    {feed?.data_type === 'gtfs'
                      ? 'GTFS Schedule'
                      : 'GTFS Realtime Schedule'}{' '}
                    / {feed?.id}
                  </Typography>
                </Grid>
              </Grid>
              <Grid item xs={12}>
                <Typography
                  sx={{
                    color: colors.blue.A700,
                    fontWeight: 'bold',
                    fontSize: { xs: 24, sm: 36 },
                  }}
                >
                  {feed?.provider?.substring(0, 100)}
                  {feed?.data_type === 'gtfs_rt' && ` - ${feed?.feed_name}`}
                </Typography>
              </Grid>
              {feed?.data_type === 'gtfs' && (
                <Grid item xs={12}>
                  <Typography
                    sx={{
                      fontWeight: 'bold',
                      fontSize: { xs: 18, sm: 24 },
                    }}
                  >
                    {feed?.feed_name}
                  </Typography>
                </Grid>
              )}
              <Grid item xs={12}>
                <Typography>
                  {latestDataset?.downloaded_at !== undefined && (
                    <span>{`Last updated on ${new Date(
                      latestDataset.downloaded_at,
                    ).toDateString()}`}</span>
                  )}
                </Typography>
              </Grid>
              {feed?.data_type === 'gtfs_rt' &&
                feed.entity_types !== undefined && (
                  <Grid item xs={12}>
                    <Typography variant='h5'>
                      {' '}
                      {feed.entity_types
                        .map(
                          (entityType) =>
                            ({
                              tu: 'Trip Updates',
                              vp: 'Vehicle Positions',
                              sa: 'Service Alerts',
                            })[entityType],
                        )
                        .join(' and ')}
                    </Typography>
                  </Grid>
                )}
              <Grid item xs={12}>
                {feed?.redirects !== undefined &&
                  feed?.redirects.length > 0 && (
                    <ContentBox
                      title={''}
                      width={{ xs: '100%' }}
                      outlineColor={colors.yellow[900]}
                    >
                      <WarningAmberOutlined />
                      This feed has been replaced with a different producer URL.
                      <a href={`/feeds/${feed.redirects[0].target_id}`}>
                        Go to the new feed here
                      </a>
                      .
                    </ContentBox>
                  )}
              </Grid>
              <Grid item xs={12}>
                {feedType === 'gtfs' && (
                  <Button
                    variant='contained'
                    sx={{ m: 2 }}
                    startIcon={<Download />}
                  >
                    <a
                      href={
                        feed?.data_type === 'gtfs'
                          ? feed?.latest_dataset?.hosted_url
                          : feed?.source_info?.producer_url
                      }
                      target='_blank'
                      className='btn-link'
                      rel='noreferrer'
                    >
                      Download latest
                    </a>
                  </Button>
                )}
                <Button
                  variant='contained'
                  sx={{ m: 2 }}
                  endIcon={<LaunchOutlined />}
                >
                  <a
                    href={feed?.source_info?.license_url}
                    target='_blank'
                    className='btn-link'
                    rel='noreferrer'
                  >
                    See License
                  </a>
                </Button>
                <Button
                  variant='contained'
                  sx={{ m: 2 }}
                  endIcon={<LaunchOutlined />}
                >
                  <a
                    href={feed?.source_info?.authentication_info_url}
                    target='_blank'
                    className='btn-link'
                    rel='noreferrer'
                  >
                    See Authentication info
                  </a>
                </Button>
              </Grid>
              <Grid item xs={12}>
                <Grid item xs={12} container rowSpacing={2}>
                  <Grid
                    container
                    direction={{ xs: 'column-reverse', md: 'row' }}
                    justifyContent={'space-between'}
                  >
                    {feed?.data_type === 'gtfs' && (
                      <ContentBox
                        title='Bounding box from stops.txt'
                        width={{ xs: '100%', md: '40%' }}
                        outlineColor={colors.blue[900]}
                      >
                        {boundingBox !== undefined && (
                          <Box width={{ xs: '100%' }}>
                            <Map polygon={boundingBox} />
                          </Box>
                        )}
                        <DataQualitySummary latestDataset={latestDataset} />
                      </ContentBox>
                    )}
                    <FeedSummary
                      feed={feed}
                      latestDataset={latestDataset}
                      width={{ xs: '100%', md: '55%' }}
                    />

                    {feed?.data_type === 'gtfs_rt' && (
                      <AssociatedGTFSRTFeeds feed={feed} />
                    )}
                  </Grid>
                </Grid>
              </Grid>
              {feed?.data_type === 'gtfs' && (
                <Grid item xs={12}>
                  <PreviousDatasets datasets={datasets} />
                </Grid>
              )}
            </Grid>
          )}
        </Box>
      </Box>
    </Container>
  );
}
