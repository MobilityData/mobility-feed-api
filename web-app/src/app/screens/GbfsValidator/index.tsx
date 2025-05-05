import { OpenInNew } from '@mui/icons-material';
import {
  Box,
  Button,
  Checkbox,
  Container,
  FormControlLabel,
  FormGroup,
  Input,
  TextField,
  Typography,
  useTheme,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import React from 'react';
import gbfsLogo from './gbfs.svg';
import githubLogo from './github.svg';
import ValidationReport from './ValidationReport';

export default function GbfsValidator(): React.ReactElement {
  const theme = useTheme();

  const test = false;
  return (
    <Box>
      <Box
        id='hero'
        sx={{
          backgroundColor: '#43E0FF',
          padding: 2,
          color: '#1d1c1c',
          marginTop: '-32px', //TODO: revisit
          height: '400px',
          display: 'flex',
          textAlign: 'center',
        }}
      >
        <Box sx={{ maxWidth: 'md', margin: 'auto', mb: '9%' }}>
          <Typography variant='h3' sx={{ fontWeight: 700, mb: 2 }}>
            GBFS Validator
          </Typography>
          <Typography sx={{ maxWidth: '30em', fontSize: '1.1rem' }}>
            The GBFS Validator is a tool that helps you validate your GBFS feeds
            against the GBFS specification.
          </Typography>
        </Box>
      </Box>
      <Box
        id='content-container'
        sx={{
          backgroundColor: theme.palette.background.default,
          height: '100%',
          pb: '50px',
          position: 'relative',
          minHeight: test ? '55vh' : 'none',
        }}
      >
        <Box
          sx={{
            position: 'absolute',
            top: '-110px',
            left: '50%',
            transform: 'translateX(-50%)',
            maxWidth: 'md',
            margin: 'auto',
          }}
        >
          <Box
            id='input-box'
            sx={{
              boxShadow: '0px 3px 0px 1px rgba(0,0,0,0.2)',
              padding: 2,
              marginTop: 2,
              borderRadius: 1,
              backgroundColor: theme.palette.background.default,
            }}
          >
            <Box
              id='input-box-header'
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <TextField
                id='outlined-basic'
                variant='outlined'
                placeholder='eg: https://example.com/gbfs.json'
                sx={{ width: '100%', mr: 2 }}
                InputProps={{
                  startAdornment: <SearchIcon></SearchIcon>,
                }}
              />
              <Button variant='contained' color='primary' sx={{ p: '12px' }}>
                Validate
              </Button>
            </Box>
            <FormGroup>
              <FormControlLabel
                control={<Checkbox />}
                label='Requires Authentication'
              />
            </FormGroup>
            <Box id='cta-buttons' sx={{ display: 'flex', gap: 2 }}>
              <Button variant='text' color='primary'>
                Broswe GBFS Feeds
              </Button>
              <Button variant='text' color='primary' endIcon={<OpenInNew />}>
                View GBFS Validator API Docs
              </Button>
            </Box>
          </Box>
          {test ? (
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

                  padding: 4,
                }}
              >
                <Box sx={{ width: '60%' }}>
                  <Typography variant='h5' sx={{ fontWeight: 700, mb: 2 }}>
                    Official GBFS Validator
                  </Typography>
                  <Typography>
                    The GBFS Validator is based on the official GBFS JSON schema
                    and is designed to help you validate your GBFS feeds against
                    the GBFS specification. For more information about GBFS or
                    the official GBFS JSON schema, please visit
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
                <Box sx={{ width: '35%', textAlign: 'center' }}>
                  <Box
                    sx={{ width: '200px' }}
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
                  mb: 2,
                  padding: 4,
                  flexDirection: 'row-reverse',
                }}
              >
                <Box sx={{ width: '60%', maxWidth: '30em' }}>
                  <Typography variant='h5' sx={{ fontWeight: 700, mb: 2 }}>
                    Contribute
                  </Typography>
                  <Typography>
                    The GBFS Validator is an open-source project and we welcome
                    contributions from the community. Special thanks to{' '}
                    <a>Tom Erik</a>
                  </Typography>
                  <Box sx={{ mt: 2 }}>
                    <Button variant='outlined' endIcon={<OpenInNew />}>
                      View Github Repository
                    </Button>
                  </Box>
                </Box>
                <Box sx={{ width: '35%', textAlign: 'center' }}>
                  <Box
                    sx={{ width: '200px' }}
                    component={'img'}
                    src={githubLogo}
                  ></Box>
                </Box>
              </Box>
            </Box>
          ) : null}
        </Box>
      </Box>
      { !test && <ValidationReport></ValidationReport>}
    </Box>
  );
}
