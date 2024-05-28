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
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  colors,
} from '@mui/material';
import {
  ContentCopy,
  ContentCopyOutlined,
  Download,
  DownloadOutlined,
  ErrorOutlineOutlined,
  LaunchOutlined,
  OpenInNewOutlined,
  ReportOutlined,
  ReportProblemOutlined,
  WarningAmberOutlined,
} from '@mui/icons-material';
import '../styles/SignUp.css';
import '../styles/FAQ.css';
import { ContentBox } from '../components/ContentBox';
import { useAppDispatch } from '../hooks';
import { loadingFeed } from '../store/feed-reducer';
import { selectUserProfile } from '../store/profile-selectors';
import {
  selectFeedData,
  selectFeedLoadingStatus,
  selectGTFSFeedData,
  selectGTFSRTFeedData,
} from '../store/feed-selectors';
import { loadingDataset } from '../store/dataset-reducer';
import {
  selectBoundingBoxFromLatestDataset,
  selectDatasetsData,
  selectLatestDatasetsData,
} from '../store/dataset-selectors';
import { Map } from '../components/Map';

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

  useEffect(() => {
    if (user?.accessToken !== undefined && feedId !== undefined) {
      dispatch(loadingFeed({ feedId, accessToken: user?.accessToken }));
      dispatch(loadingDataset({ feedId, accessToken: user?.accessToken }));
    }
  }, []);

  const renderFeedSummary = (): JSX.Element => (
    <ContentBox
      width={{ xs: '100%', md: '50%' }}
      title={'Feed Summary'}
      outlineColor={colors.indigo[500]}
    >
      <TableContainer>
        <Table>
          <TableBody>
            <TableRow>
              <TableCell
                sx={{ fontSize: 14, fontWeight: 'bold', border: 'none' }}
              >
                Producer download URL:
              </TableCell>
              <TableCell sx={{ border: 'none' }}>
                <Button
                  sx={{ textOverflow: 'ellipsis' }}
                  variant='outlined'
                  endIcon={<ContentCopy />}
                  onClick={() => {
                    if (feed?.source_info?.producer_url !== undefined) {
                      void navigator.clipboard
                        .writeText(feed?.source_info?.producer_url)
                        .then((value) => {});
                    }
                  }}
                >
                  {feed?.source_info?.producer_url}
                </Button>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell
                sx={{ fontSize: 14, fontWeight: 'bold', border: 'none' }}
              >
                Data type:
              </TableCell>
              <TableCell sx={{ border: 'none' }}>
                <Button sx={{ textOverflow: 'ellipsis' }} variant='outlined'>
                  {feed?.data_type === 'gtfs' && 'GTFS'}
                  {feed?.data_type === 'gtfs_rt' && 'GTFS Realtime'}
                </Button>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell
                sx={{ fontSize: 14, fontWeight: 'bold', border: 'none' }}
              >
                Location:
              </TableCell>
              <TableCell sx={{ border: 'none' }}>
                {feed?.locations !== undefined
                  ? Object.values(feed?.locations[0])
                      .filter((v) => v !== null)
                      .reverse()
                      .join(', ')
                  : ''}
              </TableCell>
            </TableRow>
            {feed?.data_type === 'gtfs' && (
              <TableRow>
                <TableCell
                  sx={{ fontSize: 14, fontWeight: 'bold', border: 'none' }}
                >
                  Last downloaded at:
                </TableCell>
                <TableCell sx={{ border: 'none' }}>
                  {feed?.data_type === 'gtfs' &&
                  feed.latest_dataset?.downloaded_at != null
                    ? new Date(
                        feed?.latest_dataset?.downloaded_at,
                      ).toUTCString()
                    : undefined}
                </TableCell>
              </TableRow>
            )}
            <TableRow>
              <TableCell
                sx={{ fontSize: 14, fontWeight: 'bold', border: 'none' }}
              >
                HTTP Auth Parameter:
              </TableCell>
              <TableCell sx={{ border: 'none' }}>
                {feed?.source_info?.api_key_parameter_name !== null
                  ? feed?.source_info?.api_key_parameter_name
                  : 'N/A'}
              </TableCell>
            </TableRow>
            {feed?.data_type === 'gtfs' && (
              <TableRow>
                <TableCell
                  sx={{ fontSize: 14, fontWeight: 'bold', border: 'none' }}
                >
                  Feed contact email:
                </TableCell>
                <TableCell sx={{ border: 'none' }}>
                  {feed?.feed_contact_email !== undefined &&
                    feed?.feed_contact_email.length > 0 && (
                      <Button
                        onClick={() => {
                          if (feed?.feed_contact_email !== undefined) {
                            void navigator.clipboard
                              .writeText(feed?.feed_contact_email)
                              .then((value) => {});
                          }
                        }}
                        sx={{ textOverflow: 'ellipsis' }}
                        variant='outlined'
                        endIcon={<ContentCopyOutlined />}
                      >
                        {feed?.feed_contact_email}
                      </Button>
                    )}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </ContentBox>
  );

  const renderDataQualitySummary = (): JSX.Element => (
    <ContentBox
      width={{ xs: '100%', md: '50%' }}
      title={'Data Quality Summary'}
      outlineColor={colors.indigo[500]}
    >
      <TableContainer>
        <TableRow>
          <TableCell>
            <Chip
              icon={<ReportOutlined />}
              label={`${
                latestDataset?.validation_report?.total_error ?? '0'
              } Error`}
              color='error'
              variant='outlined'
            />
            <Chip
              icon={<ReportProblemOutlined />}
              label={`${
                latestDataset?.validation_report?.total_warning ?? '0'
              } Warning`}
              color='warning'
              variant='outlined'
            />
            <Chip
              icon={<ErrorOutlineOutlined />}
              label={`${
                latestDataset?.validation_report?.total_info ?? '0'
              } Info Notices`}
              color='primary'
              variant='outlined'
            />
          </TableCell>
        </TableRow>
        <TableRow>
          {latestDataset?.validation_report?.url_html !== undefined && (
            <TableCell>
              <span style={{ display: 'flex' }}>
                <a
                  href={`${latestDataset?.validation_report?.url_html}`}
                  target='_blank'
                  rel='noreferrer'
                >
                  Open Full Report
                </a>
                <OpenInNewOutlined />
              </span>
            </TableCell>
          )}
          {latestDataset?.validation_report?.url_json !== undefined && (
            <TableCell>
              <span style={{ display: 'flex' }}>
                <a
                  href={`${latestDataset?.validation_report?.url_json}`}
                  target='_blank'
                  rel='noreferrer'
                >
                  Open JSON Report
                </a>
                <OpenInNewOutlined />
              </span>
            </TableCell>
          )}
        </TableRow>
      </TableContainer>
    </ContentBox>
  );

  const renderFeaturesList = (): JSX.Element => (
    <ContentBox
      width={{ xs: '100%', md: '50%' }}
      title={'Features List'}
      outlineColor={colors.indigo[500]}
    >
      <TableContainer>
        <TableBody>
          {latestDataset?.validation_report?.features !== undefined &&
            latestDataset?.validation_report?.features?.length > 0 && (
              <TableRow>
                <TableCell>
                  <b>Feature</b>
                </TableCell>
              </TableRow>
            )}
          {latestDataset?.validation_report?.features?.map((v) => (
            <TableRow key={v}>
              <TableCell>{v}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </TableContainer>
    </ContentBox>
  );

  const renderAssociatedGTFSFeed = (): JSX.Element => (
    <ContentBox
      width={{ xs: '100%', md: '50%' }}
      title={'Associated GTFS Schedule Feed'}
      outlineColor={colors.indigo[500]}
    >
      <TableContainer>
        <TableBody>
          {feed?.data_type === 'gtfs_rt' &&
            feed?.feed_references?.map((feedRef) => {
              return (
                <TableRow key={feedRef}>
                  <TableCell>
                    <span style={{ display: 'flex' }}>
                      <a href={`/feeds/${feedRef}`} rel='noreferrer'>
                        {feedRef}
                      </a>
                      <OpenInNewOutlined />
                    </span>
                  </TableCell>
                </TableRow>
              );
            })}
        </TableBody>
      </TableContainer>
    </ContentBox>
  );

  const renderPreviousDatasets = (): JSX.Element => (
    <ContentBox
      width={{ xs: '100%' }}
      title={'Previous Datasets'}
      outlineColor={colors.indigo[500]}
    >
      <TableContainer>
        <TableBody>
          {datasets?.map((dataset) => (
            <TableRow key={dataset.id}>
              {dataset.downloaded_at != null && (
                <TableCell>
                  {new Date(dataset.downloaded_at).toDateString()}
                </TableCell>
              )}
              <TableCell>
                <span style={{ display: 'flex' }}>
                  <a href={dataset.hosted_url}>Download Dataset</a>
                  <DownloadOutlined />
                </span>
              </TableCell>
              <TableCell>
                <div>
                  <Chip
                    icon={<ReportOutlined />}
                    label={`${
                      dataset?.validation_report?.total_error ?? '0'
                    } Error`}
                    color='error'
                    variant='outlined'
                  />
                  <Chip
                    icon={<ReportProblemOutlined />}
                    label={`${
                      dataset?.validation_report?.total_warning ?? '0'
                    } Warning`}
                    color='warning'
                    variant='outlined'
                  />
                  <Chip
                    icon={<ErrorOutlineOutlined />}
                    label={`${
                      dataset?.validation_report?.total_info ?? '0'
                    } Info Notices`}
                    color='primary'
                    variant='outlined'
                  />
                </div>
              </TableCell>
              {dataset.validation_report != null &&
                dataset.validation_report !== undefined && (
                  <TableCell>
                    <span style={{ display: 'flex' }}>
                      <a
                        href={`${dataset?.validation_report?.url_html}`}
                        target='_blank'
                        rel='noreferrer'
                      >
                        Open Full Report
                      </a>
                      <OpenInNewOutlined />
                    </span>
                  </TableCell>
                )}
              {dataset.validation_report != null &&
                dataset.validation_report !== undefined && (
                  <TableCell>
                    <a
                      href={`${dataset?.validation_report?.url_json}`}
                      target='_blank'
                      rel='noreferrer'
                    >
                      Open JSON Report <OpenInNewOutlined />
                    </a>
                  </TableCell>
                )}
            </TableRow>
          ))}
        </TableBody>
      </TableContainer>
    </ContentBox>
  );

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
                      Go to the new feed here.
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
                    {renderFeedSummary()}
                    <Box width={{ xs: '100%', md: '40%' }}>
                      {boundingBox !== undefined && (
                        <Map polygon={boundingBox} />
                      )}
                    </Box>
                  </Grid>
                  {feed?.data_type === 'gtfs' && (
                    <Grid item xs={12}>
                      {renderDataQualitySummary()}
                    </Grid>
                  )}
                  {feed?.data_type === 'gtfs' && (
                    <Grid item xs={12}>
                      {renderFeaturesList()}
                    </Grid>
                  )}
                  {feed?.data_type === 'gtfs_rt' && (
                    <Grid item xs={12}>
                      {renderAssociatedGTFSFeed()}
                    </Grid>
                  )}
                </Grid>
              </Grid>
              {feed?.data_type === 'gtfs' && (
                <Grid item xs={12}>
                  {renderPreviousDatasets()}
                </Grid>
              )}
            </Grid>
          )}
        </Box>
      </Box>
    </Container>
  );
}
