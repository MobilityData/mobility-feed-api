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
import { useNavigate } from 'react-router-dom';
import { useState, type KeyboardEvent } from 'react';

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

export default function Home(): React.ReactElement {
  const [searchInputValue, setSearchInputValue] = useState('');
  const navigate = useNavigate();

  const handleSearch = (): void => {
    if (searchInputValue.trim().length > 0) {
      navigate(`/feeds/q=${encodeURIComponent(searchInputValue)}`);
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>): void => {
    if (event.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <Container component='main' sx={{ width: '100vw', m: 0 }}>
      <CssBaseline />
      <Box
        sx={{
          mt: 12,
          px: 6,
          display: 'flex',
          flexDirection: 'column',
          width: '100vw',
        }}
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
          GTFS feeds from <span style={{ color: '#3859FA' }}>70</span>{' '}
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
            placeholder='ex. Boston'
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
            margin: '60px 0',
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
            buttonHref='/feeds'
            buttonText='Add a feed'
          />
          <ActionBox
            IconComponent={PowerOutlined}
            iconHeight='70px'
            buttonHref='/feeds'
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
            The Mobility Database catalogs is a repository of 2000+ mobility
            feeds across the world. It has over 150 updated feeds previously
            unavailable on TransitFeeds (OpenMobilityData).
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
