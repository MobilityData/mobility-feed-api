import * as React from 'react';
import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import CssBaseline from '@mui/material/CssBaseline';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
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
import {
  Chip,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  colors,
} from '@mui/material';

import '../styles/SignUp.css';
import '../styles/FAQ.css';
import { ContentBox } from '../components/ContentBox';
import { useAppDispatch } from '../hooks';
import { loadingFeed } from '../store/feed-reducer';
import { useSelector } from 'react-redux';
import { selectUserProfile } from '../store/profile-selectors';
import {
  selectFeedData,
  selectGTFSFeedData,
  selectGTFSRTFeedData,
} from '../store/feed-selectors';
import { loadingDataset } from '../store/dataset-reducer';
import {
  selectBoundingBoxFromLatestDataset,
  selectDatasetsData,
  selectLatestDatasetsData,
} from '../store/dataset-selectors';
import { DATASET_FEATURES_FILES_MAPPING } from '../utils/consts';
import { Map } from '../components/Map';

export default function Feed(): React.ReactElement {
  const { feedId } = useParams();
  const user = useSelector(selectUserProfile);
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
      dispatch(
        loadingFeed({
          feedId,
          accessToken: user?.accessToken,
        }),
      );
      dispatch(
        loadingDataset({
          feedId,
          accessToken: user?.accessToken,
        }),
      );
    }
  }, []);

  return (
    <Container component='main' sx={{ width: '100vw', m: 0 }}>
      <CssBaseline />
      <Box
        sx={{
          mt: 12,
          display: 'flex',
          flexDirection: 'column',
          m: 10,
        }}
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
          <Grid container spacing={2}>
            <Grid item xs={12}></Grid>
            <Grid item xs={12}>
              <Typography>
                Feeds /{' '}
                {feedType === 'gtfs'
                  ? 'GTFS Schedule'
                  : 'GTFS Realtime Schedule'}
                {' / '}
                {feed?.id}{' '}
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
              {feed?.redirects !== undefined && feed?.redirects.length > 0 && (
                <ContentBox
                  title={''}
                  width={{ xs: '100%' }}
                  outlineColor={colors.yellow[900]}
                >
                  <WarningAmberOutlined />
                  This feed has been replaced with a different producer URL. Go
                  to the new feed here.
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
                              sx={{
                                fontSize: 14,
                                fontWeight: 'bold',
                                border: 'none',
                              }}
                            >
                              Producer download URL:
                            </TableCell>
                            <TableCell sx={{ border: 'none' }}>
                              <Button
                                sx={{
                                  textOverflow: 'ellipsis',
                                }}
                                variant='outlined'
                                endIcon={<ContentCopy />}
                                onClick={() => {
                                  if (
                                    feed?.source_info?.producer_url !==
                                    undefined
                                  ) {
                                    void navigator.clipboard
                                      .writeText(
                                        feed?.source_info?.producer_url,
                                      )
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
                              sx={{
                                fontSize: 14,
                                fontWeight: 'bold',
                                border: 'none',
                              }}
                            >
                              Data type:
                            </TableCell>
                            <TableCell sx={{ border: 'none' }}>
                              <Button
                                sx={{
                                  textOverflow: 'ellipsis',
                                }}
                                variant='outlined'
                              >
                                {feed?.data_type === 'gtfs' && 'GTFS'}
                                {feed?.data_type === 'gtfs_rt' &&
                                  'GTFS Realtime'}
                              </Button>
                            </TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell
                              sx={{
                                fontSize: 14,
                                fontWeight: 'bold',
                                border: 'none',
                              }}
                            >
                              Location:
                            </TableCell>
                            <TableCell sx={{ border: 'none' }}>
                              {/* Join locations array into one string */}
                              {feed?.locations !== undefined
                                ? Object.values(feed?.locations[0])
                                    .filter((v) => v !== null)
                                    .reverse()
                                    .join(', ')
                                : ''}
                            </TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell
                              sx={{
                                fontSize: 14,
                                fontWeight: 'bold',
                                border: 'none',
                              }}
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
                          <TableRow>
                            <TableCell
                              sx={{
                                fontSize: 14,
                                fontWeight: 'bold',
                                border: 'none',
                              }}
                            >
                              HTTP Auth Parameter:
                            </TableCell>
                            <TableCell sx={{ border: 'none' }}>
                              {feed?.source_info?.api_key_parameter_name !==
                              null
                                ? feed?.source_info?.api_key_parameter_name
                                : 'N/A'}
                            </TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell
                              sx={{
                                fontSize: 14,
                                fontWeight: 'bold',
                                border: 'none',
                              }}
                            >
                              Feed contact email:
                            </TableCell>
                            <TableCell sx={{ border: 'none' }}>
                              {feed?.feed_contact_email !== undefined && (
                                <Button
                                  onClick={() => {
                                    if (
                                      feed?.feed_contact_email !== undefined
                                    ) {
                                      void navigator.clipboard
                                        .writeText(feed?.feed_contact_email)
                                        .then((value) => {});
                                    }
                                  }}
                                  sx={{
                                    textOverflow: 'ellipsis',
                                  }}
                                  variant='outlined'
                                  endIcon={<ContentCopyOutlined />}
                                >
                                  {feed?.feed_contact_email}
                                </Button>
                              )}
                            </TableCell>
                          </TableRow>
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </ContentBox>
                  <Box width={{ xs: '100%', md: '40%' }}>
                    {boundingBox !== undefined && <Map polygon={boundingBox} />}
                  </Box>
                </Grid>
                {feed?.data_type === 'gtfs' && (
                  <Grid item xs={12}>
                    <ContentBox
                      width={{ xs: '100%', md: '50%' }}
                      title={'Data Quality Summary'}
                      outlineColor={colors.indigo[500]}
                    >
                      <TableRow>
                        <TableCell>
                          <Chip
                            icon={<ReportOutlined />}
                            label={`${
                              latestDataset?.validation_report?.total_error ??
                              '0'
                            } Error`}
                            color='error'
                            variant='outlined'
                          />
                          <Chip
                            icon={<ReportProblemOutlined />}
                            label={`${
                              latestDataset?.validation_report?.total_warning ??
                              '0'
                            } Warning`}
                            color='warning'
                            variant='outlined'
                          />
                          <Chip
                            icon={<ErrorOutlineOutlined />}
                            label={`${
                              latestDataset?.validation_report?.total_info ??
                              '0'
                            } Info Notices`}
                            color='primary'
                            variant='outlined'
                          />
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>
                          <a
                            href={`${latestDataset?.validation_report?.url_html}`}
                            target='_blank'
                            rel='noreferrer'
                          >
                            Open Full Report <OpenInNewOutlined />
                          </a>
                        </TableCell>
                        <TableCell>
                          <a
                            href={`${latestDataset?.validation_report?.url_json}`}
                            target='_blank'
                            rel='noreferrer'
                          >
                            Open JSON Report <OpenInNewOutlined />
                          </a>
                        </TableCell>
                      </TableRow>
                    </ContentBox>
                  </Grid>
                )}
                {feed?.data_type === 'gtfs' && (
                  <Grid item xs={12}>
                    <ContentBox
                      width={{ xs: '100%', md: '50%' }}
                      title={'Features List'}
                      outlineColor={colors.indigo[500]}
                    >
                      <TableContainer>
                        <TableRow>
                          <TableCell>
                            <b>Feature</b>
                          </TableCell>
                          <TableCell>
                            <b>File or Field Associated</b>
                          </TableCell>
                        </TableRow>
                        {latestDataset?.validation_report?.features?.map(
                          (v) => (
                            <TableRow key={v}>
                              <TableCell>{v}</TableCell>
                              <TableCell>
                                {DATASET_FEATURES_FILES_MAPPING.getFeedFileByFeatureName(
                                  v,
                                )}
                              </TableCell>
                            </TableRow>
                          ),
                        )}
                      </TableContainer>
                    </ContentBox>
                  </Grid>
                )}
                {feed?.data_type === 'gtfs_rt' && (
                  <Grid item xs={12}>
                    <ContentBox
                      width={{ xs: '100%', md: '50%' }}
                      title={'Associated GTFS Schedule Feed'}
                      outlineColor={colors.indigo[500]}
                    >
                      <TableContainer>
                        {feed.feed_references?.map((feedRef) => {
                          return (
                            <TableRow key={feedRef}>
                              <TableCell>
                                <a
                                  target='_blank'
                                  href={`/feeds/${feedRef}`}
                                  rel='noreferrer'
                                >
                                  {feedRef} <OpenInNewOutlined />
                                </a>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableContainer>
                    </ContentBox>
                  </Grid>
                )}
              </Grid>
            </Grid>
            {feed?.data_type === 'gtfs' && (
              <Grid item xs={12}>
                <ContentBox
                  width={{ xs: '100%' }}
                  title={'Previous Datasets'}
                  outlineColor={colors.indigo[500]}
                >
                  <TableContainer>
                    {datasets?.map((dataset) => (
                      <TableRow key={dataset.id}>
                        {dataset.downloaded_at != null && (
                          <TableCell>
                            {new Date(dataset.downloaded_at).toDateString()}
                          </TableCell>
                        )}
                        <TableCell>
                          <a
                            href={dataset.hosted_url}
                            className='flex items-center'
                          >
                            Download Dataset <DownloadOutlined />
                          </a>
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
                        {dataset.validation_report != null && (
                          <TableCell>
                            <a
                              href={`${dataset?.validation_report?.url_html}`}
                              target='_blank'
                              rel='noreferrer'
                            >
                              Open Full Report <OpenInNewOutlined />
                            </a>
                          </TableCell>
                        )}
                        {dataset.validation_report != null && (
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
                  </TableContainer>
                </ContentBox>
              </Grid>
            )}
          </Grid>
        </Box>
      </Box>
    </Container>
  );
}
