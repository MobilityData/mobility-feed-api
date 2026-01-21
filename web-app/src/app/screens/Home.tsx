import * as React from 'react';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import {
  Button,
  Divider,
  InputAdornment,
  TextField,
  useTheme,
} from '@mui/material';
import {
  Search,
  CheckCircleOutlineOutlined,
  PowerOutlined,
} from '@mui/icons-material';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { WEB_VALIDATOR_LINK } from '../constants/Navigation';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import '../styles/TextShimmer.css';

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
}: ActionBoxProps): React.ReactElement => (
  <Box
    sx={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      flexGrow: 1,
      flexBasis: 0,
      minWidth: 0,
    }}
  >
    <IconComponent sx={{ width: '100%', height: iconHeight }} />
    <Button variant='contained' href={buttonHref} sx={{ m: 2, px: 2 }}>
      {buttonText}
    </Button>
  </Box>
);

function Component(): React.ReactElement {
  const [searchInputValue, setSearchInputValue] = useState('');
  const navigate = useNavigate();
  const theme = useTheme();

  const handleSearch = (): void => {
    const encodedURI = encodeURIComponent(searchInputValue.trim());
    if (encodedURI.length === 0) {
      navigate('/feeds');
    } else {
      navigate(`/feeds?q=${encodedURI}`);
    }
  };

  const handleKeyDown = (
    event: React.KeyboardEvent<HTMLInputElement>,
  ): void => {
    if (event.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <Container component='main' sx={{ px: { xs: 0, md: 3 } }}>
      <CssBaseline />
      <Box
        sx={{
          mt: 6,
          display: 'flex',
          flexDirection: 'column',
        }}
        mx={{ xs: '20px', m: 'auto' }}
        maxWidth={{ xs: '100%', md: '1600px' }}
      >
        <Typography
          component={'h1'}
          sx={{
            fontSize: {
              xs: '36px',
              sm: '48px',
            },
            fontStyle: 'normal',
            fontWeight: 700,
            lineHeight: 'normal',
            textAlign: 'center',
          }}
          data-testid='home-title'
          className='shimmer'
        >
          Explore and Access Global Transit Data
        </Typography>
        <Typography
          component='h2'
          variant='h5'
          sx={{
            textAlign: 'center',
            fontWeight: 700,
            mt: 4,
          }}
        >
          Currently serving over
          <Box
            component='span'
            sx={{ fontSize: 30, color: theme.palette.primary.main, mx: 1 }}
          >
            4000
          </Box>
          transportation data feeds from over
          <Box
            component='span'
            sx={{ fontSize: 30, color: theme.palette.primary.main, mx: 1 }}
          >
            75
          </Box>
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
              fieldset: {
                borderColor: theme.palette.primary.main,
              },
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
            justifyContent: 'center',
            flexDirection: { xs: 'column', sm: 'row' },
            width: '700px',
            maxWidth: '100%',
            margin: 'auto',
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
        <Box
          sx={{
            background: theme.palette.background.paper,
            borderRadius: '6px 0px 0px 6px',
            p: {
              xs: 2,
              sm: 4,
            },
            fontSize: '18px',
            fontWeight: 700,
            mr: 0,
            mt: 5,
          }}
        >
          The Mobility Database is an open data catalog including over 4000
          GTFS, GTFS Realtime, and GBFS feeds in over 75 countries. Whether
          you’re a transportation operator, a researcher studying public transit
          and shared mobility trends, or a maps app needing reliable data to use
          with your application, the Mobility Database has everything you need
          in one central location.
          <br />
          <br />
          Our database integrates with
          <Button
            variant='text'
            className='inline'
            href={WEB_VALIDATOR_LINK}
            rel='noreferrer'
            target='_blank'
            endIcon={<OpenInNewIcon />}
          >
            the Canonical GTFS Schedule Validator
          </Button>
          and
          <Button
            variant='text'
            className='inline'
            href='https://gbfs-validator.mobilitydata.org/'
            rel='noreferrer'
            target='_blank'
            endIcon={<OpenInNewIcon />}
          >
            the GBFS Validator
          </Button>
          to provide detailed data quality reports on every feed.
        </Box>
      </Box>
    </Container>
  );
}

export default function Home(): React.ReactElement {
  return <Component />;
}
