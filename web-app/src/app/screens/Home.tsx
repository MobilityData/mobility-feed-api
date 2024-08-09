import * as React from 'react';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import '../styles/SignUp.css';
import {
  Button,
  Divider,
  Grid,
  InputAdornment,
  TextField,
} from '@mui/material';
import {
  Search,
  CheckCircleOutlineOutlined,
  PowerOutlined,
} from '@mui/icons-material';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import LegacyHome from './LegacyHome';
import { useRemoteConfig } from '../context/RemoteConfigProvider';

interface ActionBoxProps {
  IconComponent: React.ElementType;
  iconHeight: string;
  buttonHref: string;
  buttonText: string;
}

const ActionBox = ({
  IconComponent,
  iconHeight,
  buttonHref,
  buttonText,
}: ActionBoxProps): JSX.Element => (
  <Box
    sx={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
    }}
  >
    <IconComponent sx={{ width: '100%', height: iconHeight }} />
    <Button variant='contained' sx={{ m: 2, px: 2 }}>
      <a href={buttonHref} className='btn-link' rel='noreferrer'>
        {buttonText}
      </a>
    </Button>
  </Box>
);

function Component(): React.ReactElement {
  const [searchInputValue, setSearchInputValue] = useState('');
  const navigate = useNavigate();

  const handleSearch = (): void => {
    navigate(`/feeds?q=${encodeURIComponent(searchInputValue)}`);
  };

  const handleKeyDown = (
    event: React.KeyboardEvent<HTMLInputElement>,
  ): void => {
    if (event.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <Container component='main'>
      <CssBaseline />
      <Box
        sx={{
          mt: 12,
          display: 'flex',
          flexDirection: 'column',
        }}
        margin={{ xs: '80px 20px', m: '80px auto' }}
        maxWidth={{ xs: '100%', m: '1600px' }}
      >
        <Typography
          sx={{
            fontSize: {
              xs: '48px',
              sm: '60px',
              md: '72px',
            },
            fontStyle: 'normal',
            fontWeight: 700,
            lineHeight: 'normal',
            textAlign: 'center',
          }}
          color='primary'
          data-testid='home-title'
        >
          The Mobility Database
        </Typography>
        <Typography
          component='h1'
          variant='h5'
          sx={{ textAlign: 'center', color: 'black', fontWeight: 700, mt: 4 }}
        >
          Currently serving over <span style={{ color: '#3859FA' }}>2000</span>{' '}
          transit data feeds from <span style={{ color: '#3859FA' }}>70</span>{' '}
          countries.
        </Typography>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
          }}
        >
          <TextField
            sx={{
              width: '80%',
              mt: 6,
            }}
            value={searchInputValue}
            onChange={(e) => {
              setSearchInputValue(e.target.value);
            }}
            onKeyDown={handleKeyDown}
            placeholder='e.g. "New York" or "Carris Metropolitana"'
            InputProps={{
              startAdornment: (
                <InputAdornment position={'start'}>
                  <Search />
                </InputAdornment>
              ),
            }}
          />
          <Button
            sx={{
              mt: 6,
              py: 1.5,
              ml: 1,
              height: 55,
              boxShadow: 0,
            }}
            variant='contained'
            color='primary'
            onClick={handleSearch}
          >
            Search
          </Button>
        </Box>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            margin: '30px 0',
            position: 'relative',
          }}
        >
          <Divider
            sx={{
              flexGrow: 1,
              backgroundColor: 'text.primary',
            }}
            variant='middle'
          />
          <Typography
            sx={{ fontWeight: 'bold', marginX: '8px' }}
            variant='body1'
          >
            or
          </Typography>
          <Divider
            sx={{
              flexGrow: 1,
              backgroundColor: 'text.primary',
              mx: '16',
            }}
            variant='middle'
          />
        </Box>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-around',
          }}
        >
          <ActionBox
            IconComponent={Search}
            iconHeight='70px'
            buttonHref='/feeds'
            buttonText='Browse Feeds'
          />
          <ActionBox
            IconComponent={CheckCircleOutlineOutlined}
            iconHeight='70px'
            buttonHref='/contribute'
            buttonText='Add a feed'
          />
          <ActionBox
            IconComponent={PowerOutlined}
            iconHeight='70px'
            buttonHref='/sign-up'
            buttonText='Sign up for the API'
          />
        </Box>

        <Grid sm={12} md={5}>
          <Box
            sx={{
              background: '#F8F5F5',
              borderRadius: '6px 0px 0px 6px',
              display: 'flex',
              alignItems: 'center',
              justifyItems: 'center',
              p: 5,
              color: 'black',
              fontSize: '18px',
              fontWeight: 700,
              mr: 0,
              mt: 5,
            }}
          >
            The Mobility Database is a directory of 2000+ mobility
            feeds across the world. It has over 250 updated feeds previously
            unavailable on TransitFeeds (OpenMobilityData) and shares data quality reports from <a href="https://gtfs-validator.mobilitydata.org/">the Canonical GTFS Schedule Validator</a>.
            <br />
            <br />
            We’re in the first phase of building a sustainable, central hub for
            mobility data internationally.
          </Box>
        </Grid>
      </Box>
    </Container>
  );
}

export default function Home(): React.ReactElement {
  const { config } = useRemoteConfig();
  if (config.enableFeedsPage) {
    return <Component />;
  }
  return <LegacyHome />;
}
