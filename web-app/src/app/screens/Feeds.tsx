import * as React from 'react';
import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import CssBaseline from '@mui/material/CssBaseline';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import { ContentCopy, Download } from '@mui/icons-material';
import {
  Chip,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
} from '@mui/material';
import '../styles/SignUp.css';
import '../styles/FAQ.css';
import { ContentBox } from '../components/ContentBox';
import { useAppDispatch } from '../hooks';
import { loadingFeed } from '../store/feed-reducer';
import { useSelector } from 'react-redux';
import { selectUserProfile } from '../store/profile-selectors';
import { selectGTFSFeedData } from '../store/feed-selectors';

export default function Feeds(): React.ReactElement {
  const { feedId } = useParams();
  const user = useSelector(selectUserProfile);
  const feed = useSelector(selectGTFSFeedData);
  console.log(feed);
  const dispatch = useAppDispatch();

  useEffect(() => {
    if (user?.accessToken !== undefined && feedId !== undefined) {
      dispatch(
        loadingFeed({
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
          width: '100vw',
          m: 10,
        }}
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
            <Grid item xs={12}>
              <Typography>Feeds / GTFS Schedule / {feed?.id} </Typography>
            </Grid>
            <Grid item xs={12}>
              <Typography variant='h3'>
                {feed?.source_info?.producer_url}
              </Typography>
            </Grid>
            <Grid item xs={12}>
              <Typography variant='h5'>{feed?.provider}</Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
              <Button
                variant='contained'
                sx={{ m: 2 }}
                startIcon={<Download />}
              >
                <a
                  href={feed?.latest_dataset?.hosted_url}
                  target='_blank'
                  className='btn-link'
                  rel='noreferrer'
                >
                  Download latest
                </a>
              </Button>
              <Button
                variant='contained'
                sx={{ m: 2 }}
                startIcon={<Download />}
              >
                <a
                  href={feed?.source_info?.license_url}
                  target='_blank'
                  className='btn-link'
                  rel='noreferrer'
                >
                  License URL
                </a>
              </Button>
              <Button
                variant='contained'
                sx={{ m: 2 }}
                startIcon={<Download />}
              >
                <a
                  href={feed?.source_info?.authentication_info_url}
                  target='_blank'
                  className='btn-link'
                  rel='noreferrer'
                >
                  Authentication info URL
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
                  <ContentBox title={'Feed Summary'}>
                    <TableContainer>
                      <Table>
                        <TableBody>
                          <TableRow>
                            <TableCell
                              sx={{
                                fontSize: 18,
                                fontWeight: 'bold',
                                border: 'none',
                              }}
                              align='right'
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
                              >
                                {feed?.source_info?.producer_url}
                              </Button>
                            </TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell
                              sx={{
                                fontSize: 18,
                                fontWeight: 'bold',
                                border: 'none',
                              }}
                              align='right'
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
                                {feed?.data_type}
                              </Button>
                            </TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell
                              sx={{
                                fontSize: 18,
                                fontWeight: 'bold',
                                border: 'none',
                              }}
                              align='right'
                            >
                              Location:
                            </TableCell>
                            <TableCell sx={{ border: 'none' }}>
                              {feed?.locations !== undefined
                                ? Object.values(feed?.locations[0]).join(', ')
                                : ''}
                            </TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell
                              sx={{
                                fontSize: 18,
                                fontWeight: 'bold',
                                border: 'none',
                              }}
                              align='right'
                            >
                              Last downloaded at:
                            </TableCell>
                            <TableCell sx={{ border: 'none' }}>
                              {feed?.latest_dataset?.downloaded_at}
                            </TableCell>
                          </TableRow>
                          <TableRow>
                            <TableCell
                              sx={{
                                fontSize: 18,
                                fontWeight: 'bold',
                                border: 'none',
                              }}
                              align='right'
                            >
                              HTTP Auth Parameter
                            </TableCell>
                            <TableCell sx={{ border: 'none' }}>
                              {feed?.source_info?.api_key_parameter_name}
                            </TableCell>
                          </TableRow>
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </ContentBox>
                  <Box>Map</Box>
                </Grid>
                <Grid item xs={12}>
                  <ContentBox title={'Data Quality Summary'}>
                    <Chip label='Error' color='error' variant='outlined' />
                    <Chip label='Warning' color='warning' variant='outlined' />
                    <Chip
                      label='Info notices'
                      color='primary'
                      variant='outlined'
                    />
                  </ContentBox>
                </Grid>
                <Grid item xs={12}>
                  <ContentBox title={'Features List'}></ContentBox>
                </Grid>
                <Grid item xs={12}>
                  <ContentBox
                    title={'Associated GTFS Realtime Feeds'}
                  ></ContentBox>
                </Grid>
                <Grid item xs={12}>
                  <ContentBox title={'Previous Datasets'}></ContentBox>
                </Grid>
              </Grid>
            </Grid>
          </Grid>
        </Box>
      </Box>
    </Container>
  );
}
