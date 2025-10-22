import { OpenInNew } from '@mui/icons-material';
import {
  Box,
  Button,
  Chip,
  Container,
  Link,
  Typography,
  useTheme,
} from '@mui/material';
import React from 'react';
import gbfsLogo from './gbfs.svg';
import githubLogo from './github.svg';
import ValidationReport from './ValidationReport';
import GbfsFeedSearchInput from './GbfsFeedSearchInput';
import { useSearchParams } from 'react-router-dom';
import { Map } from '../../components/Map';
import {
  gbfsValidatorHeroBg,
  PromotionRow,
  PromotionTextColumn,
} from './validator.styles';

export default function GbfsValidator(): React.ReactElement {
  const theme = useTheme();
  const [searchParams] = useSearchParams();
  const isInSearchState = searchParams.has('AutoDiscoveryUrl');

  return (
    <Box>
      {!isInSearchState ? (
        <>
          <Box
            id='hero'
            sx={{
              ...gbfsValidatorHeroBg,
              padding: 2,
              color: theme.palette.common.black,
              marginTop: '-32px',
              height: '400px',
              display: 'flex',
              textAlign: 'center',
            }}
          >
            <Box sx={{ maxWidth: 'md', margin: 'auto', mb: '120px' }}>
              <Typography variant='h3' sx={{ fontWeight: 700, mb: 2 }}>
                GBFS Validator
              </Typography>
              <Typography
                sx={{ maxWidth: '26em', fontSize: theme.typography.h6 }}
              >
                Validate and visualize GBFS feeds against the official GBFS
                specification
              </Typography>
            </Box>
          </Box>
          <Box
            id='content-container'
            sx={{
              mx: 2,
              display: 'flex',
              justifyContent: 'center',
            }}
          >
            <Box
              sx={{
                mt: '-110px',
                maxWidth: 'md',
                width: '100%',
              }}
            >
              <GbfsFeedSearchInput></GbfsFeedSearchInput>
              <Box
                id='info-container'
                sx={{
                  mt: 6,
                  padding: 2,
                }}
              >
                <PromotionRow>
                  <PromotionTextColumn>
                    <Typography variant='h5' sx={{ fontWeight: 700, mb: 2 }}>
                      Validate and Explore GBFS Feeds
                    </Typography>
                    <Typography
                      sx={{
                        maxWidth: 'clamp(45ch, 60%, 75ch)',
                        fontSize: theme.typography.h6,
                      }}
                    >
                      GBFS Validator & Visualizer lets you instantly check GBFS
                      feeds against the official specification — and see the
                      results on an interactive map. For more information about
                      GBFS or the official specification, please visit
                    </Typography>
                    <Box
                      sx={{
                        mt: 3,
                        display: 'flex',
                        gap: 2,
                        justifyContent: { xs: 'center', md: 'flex-start' },
                        flexWrap: 'wrap',
                      }}
                    >
                      <Button
                        variant='outlined'
                        endIcon={<OpenInNew />}
                        href='https://github.com/MobilityData/gbfs-json-schema'
                        target='_blank'
                        rel='noreferrer'
                      >
                        GBFS Schema Repository
                      </Button>
                      <Button
                        variant='outlined'
                        endIcon={<OpenInNew />}
                        href='https://gbfs.org'
                        target='_blank'
                        rel='noreferrer'
                      >
                        GBFS.org
                      </Button>
                    </Box>
                  </PromotionTextColumn>
                  <Box
                    sx={{
                      width: { xs: '100%', md: '40%' },
                      textAlign: 'center',
                    }}
                  >
                    <Box
                      sx={{ width: '225px' }}
                      component={'img'}
                      src={gbfsLogo}
                      alt='gbfs logo'
                    ></Box>
                  </Box>
                </PromotionRow>
                <PromotionRow reverse sx={{ mt: 8 }}>
                  <PromotionTextColumn>
                    <Typography variant='h5' sx={{ fontWeight: 700, mb: 2 }}>
                      Contribute
                    </Typography>
                    <Typography
                      sx={{
                        maxWidth: 'clamp(45ch, 60%, 75ch)',
                        fontSize: theme.typography.h6,
                      }}
                    >
                      The GBFS Validator & Visualizer is an open-source tool. We
                      welcome contributions from the community — whether through
                      feature improvements, testing, or documentation. Special
                      thanks to{' '}
                      <Link
                        href='https://entur.no/'
                        target='_blank'
                        rel='noreferrer'
                      >
                        Entur
                      </Link>{' '}
                      for their outstanding work on the validation engine
                    </Typography>
                    <Box sx={{ mt: 3 }}>
                      <Button
                        variant='outlined'
                        endIcon={<OpenInNew />}
                        href='https://github.com/MobilityData/gbfs-validator-java'
                        target='_blank'
                        rel='noreferrer'
                      >
                        Explore on Github
                      </Button>
                    </Box>
                  </PromotionTextColumn>
                  <Box
                    sx={{
                      width: { xs: '100%', md: '40%' },
                      textAlign: 'center',
                    }}
                  >
                    <Box
                      sx={{ width: '225px' }}
                      component={'img'}
                      src={githubLogo}
                      alt='github logo'
                    ></Box>
                  </Box>
                </PromotionRow>
              </Box>
            </Box>
          </Box>
        </>
      ) : null}
      {isInSearchState && (
        <>
          <Box
            sx={{
              background: '#43E0FF',
              p: 2,
              borderRadius: 1,
              mb: 2,
              mt: '-32px',
            }}
          >
            <Container maxWidth='lg' sx={{ mb: 4, mt: 2 }}>
              <GbfsFeedSearchInput></GbfsFeedSearchInput>
            </Container>
          </Box>
          <Container maxWidth='lg' sx={{ mb: 4, mt: 2 }}>
            <Box sx={{ mt: 4, textAlign: 'center' }}>
              <Typography variant='h6'>GBFS Feed Validation</Typography>
              {/* <Typography variant='h4'>{searchParams.get('AutoDiscoveryUrl')}</Typography> */}
              <Typography variant='h5' sx={{ fontWeight: 700, mb: 2 }}>
                https://tor.publicbikesystem.net/customer/gbfs/v2/gbfs.json
              </Typography>
            </Box>
            <Box
              sx={{
                display: 'flex',
                gap: 1,
                mb: 2,
                ml: 2,
                flexWrap: 'wrap',
                justifyContent: 'center',
              }}
            >
              <Chip label='Version 2.2' color='primary' />
              <Chip label='Valid Feed' color='success' />
              <Chip label='Invalid Feed' color='error' />
              <Chip
                label='3 Total Errors'
                color='error'
                variant='outlined'
              />{' '}
              <Chip label='2 Files Errors' color='error' variant='outlined' />
              <Chip label='validator v1.2' variant='outlined' />
            </Box>

            <Map polygon={[{ lat: 37.7749, lng: -122.4194 }]}></Map>
            <Box textAlign={'right'}>
              <Button variant='outlined'>View Full Map Details</Button>
            </Box>
            <ValidationReport></ValidationReport>
          </Container>
        </>
      )}
    </Box>
  );
}
