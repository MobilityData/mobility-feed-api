import { OpenInNew } from '@mui/icons-material';
import { Box, Button, Container, Typography, useTheme } from '@mui/material';
import React from 'react';
import gbfsLogo from './gbfs.svg';
import githubLogo from './github.svg';
import ValidationReport from './ValidationReport';
import GbfsFeedSearchInput from './GbfsFeedSearchInput';
import { useSearchParams } from 'react-router-dom';
import { Map } from '../../components/Map';
import { gbfsValidatorHeroBg } from './validator.styles';

export default function GbfsValidator(): React.ReactElement {
  const theme = useTheme();
  const [searchParams, setSearchParams] = useSearchParams();
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
              color: '#1d1c1c',
              marginTop: '-32px', //TODO: revisit
              height: '400px',
              display: 'flex',
              textAlign: 'center',
            }}
          >
            <Box sx={{ maxWidth: 'md', margin: 'auto', mb: '120px' }}>
              <Typography variant='h3' sx={{ fontWeight: 700, mb: 2 }}>
                GBFS Validator
              </Typography>
              <Typography sx={{ maxWidth: '30em', fontSize: '20px' }}>
                The GBFS Validator is a tool that helps you validate your GBFS
                feeds against the GBFS specification.
              </Typography>
            </Box>
          </Box>
          <Box
            id='content-container'
            sx={{
              backgroundColor: theme.palette.background.default,
              height: '100%',
              pb: '50px',
              mx: 2,
              position: 'relative',
              minHeight: !isInSearchState ? '55vh' : 'none',
            }}
          >
            <Box
              sx={{
                position: 'absolute',
                top: '-110px',
                left: '50%',
                transform: 'translateX(-50%)',
                maxWidth: 'md',
                width: '100%',
                margin: 'auto',
              }}
            >
              <GbfsFeedSearchInput></GbfsFeedSearchInput>

              <Box
                id='info-container'
                sx={{
                  mt: 4,
                  backgroundColor: theme.palette.background.default,
                  padding: 2,
                  height: '100%',
                }}
              >
                <Box
                  id='row'
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    mt: 4,
                  }}
                >
                  <Box sx={{ width: '55%' }}>
                    <Typography variant='h5' sx={{ fontWeight: 700, mb: 2 }}>
                      Official GBFS Validator
                    </Typography>
                    <Typography sx={{maxWidth: 'clamp(45ch, 60%, 75ch)', fontSize: '20px' }}>
                      The GBFS Validator is based on the official GBFS JSON
                      schema and is designed to help you validate your GBFS
                      feeds against the GBFS specification. For more information
                      about GBFS or the official GBFS JSON schema, please visit
                    </Typography>
                    <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
                      <Button variant='outlined' endIcon={<OpenInNew />}>
                        GBFS Schema Repository
                      </Button>
                      <Button variant='outlined' endIcon={<OpenInNew />}>
                        GBFS.org
                      </Button>
                    </Box>
                  </Box>
                  <Box sx={{ width: '40%', textAlign: 'center' }}>
                    <Box
                      sx={{ width: '225px' }}
                      component={'img'}
                      src={gbfsLogo}
                    ></Box>
                  </Box>
                </Box>
                <Box
                  id='row'
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    mb: 4,
                    mt: 6,
                    flexDirection: 'row-reverse',
                  }}
                >
                  <Box sx={{ width: '55%', maxWidth: '30em' }}>
                    <Typography variant='h5' sx={{ fontWeight: 700, mb: 2 }}>
                      Contribute
                    </Typography>
                    <Typography sx={{maxWidth: 'clamp(45ch, 60%, 75ch)', fontSize: '20px' }}>
                      The GBFS Validator is an open-source project and we
                      welcome contributions from the community. Special thanks
                      to <a>Tom Erik</a>
                    </Typography>
                    <Box sx={{ mt: 2 }}>
                      <Button variant='outlined' endIcon={<OpenInNew />}>
                        View Github Repository
                      </Button>
                    </Box>
                  </Box>
                  <Box sx={{ width: '40%', textAlign: 'center' }}>
                    <Box
                      sx={{ width: '225px' }}
                      component={'img'}
                      src={githubLogo}
                    ></Box>
                  </Box>
                </Box>
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
