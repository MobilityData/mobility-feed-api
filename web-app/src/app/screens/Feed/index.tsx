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
import AssociatedGTFSFeeds from './AssociatedGTFSFeeds';
import FeaturesList from './FeaturesList';
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
  const isAuthenticated = useSelector(selectIsAuthenticated);

  useEffect(() => {
    if (
      isAuthenticated &&
      user?.accessToken !== undefined &&
      feedId !== undefined
    ) {
      dispatch(loadingFeed({ feedId, accessToken: user?.accessToken }));
      dispatch(loadingDataset({ feedId, accessToken: user?.accessToken }));
    }
  }, [isAuthenticated]);

  return (
    <Container component='main' sx={{ width: '100vw', m: 0 }}>
      <CssBaseline />
      <Box
        sx={{ mt: 12, display: 'flex', flexDirection: 'column', m: 10 }}
        margin={{ xs: '0', sm: '80px' }}
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
              <Grid item xs={12}></Grid>
              <Grid item xs={12}>
                <Typography>
                  Feeds /{' '}
                  {feedType === 'gtfs'
                    ? 'GTFS Schedule'
                    : 'GTFS Realtime Schedule'}{' '}
                  / {feed?.id}
                </Typography>
              </Grid>
              <Grid item xs={12}>
                <Typography sx={{ typography: { xs: 'h4', sm: 'h3' } }}>
                  {feed?.provider?.substring(0, 100)}
                </Typography>
              </Grid>
              {feed?.feed_name ?? (
                <Grid item xs={12}>
                  <Typography variant='h5'>{feed?.feed_name}</Typography>
                </Grid>
              )}
              {feedType === 'gtfs_rt' && (
                <Grid item xs={12}>
                  <Typography variant='h5'>Vehicle Positions</Typography>
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
                    <FeedSummary feed={feed} />
                    <Box width={{ xs: '100%', md: '40%' }}>
                      {boundingBox !== undefined && (
                        <Map polygon={boundingBox} />
                      )}
                    </Box>
                  </Grid>
                  {feed?.data_type === 'gtfs' && (
                    <Grid item xs={12}>
                      <DataQualitySummary latestDataset={latestDataset} />
                    </Grid>
                  )}
                  {feed?.data_type === 'gtfs' && (
                    <Grid item xs={12}>
                      <FeaturesList latestDataset={latestDataset} />
                    </Grid>
                  )}
                  {feed?.data_type === 'gtfs_rt' && (
                    <Grid item xs={12}>
                      <AssociatedGTFSFeeds feed={feed} />
                    </Grid>
                  )}
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
