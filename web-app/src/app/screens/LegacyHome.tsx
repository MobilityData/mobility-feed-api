import * as React from 'react';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import '../styles/SignUp.css';
import { Button, Grid } from '@mui/material';
import { Download, Login } from '@mui/icons-material';

export default function Home(): React.ReactElement {
  return (
    <Container component='main' sx={{ width: '100vw', m: 0 }}>
      <CssBaseline />
      <Box
        sx={{
          mt: 12,
          display: 'flex',
          flexDirection: 'column',
          width: '100vw',
        }}
      >
        <Grid container spacing={0}>
          <Grid item sm={12} md={7}>
            <Typography
              sx={{
                fontSize: {
                  xs: '48px',
                  sm: '60px',
                  md: '72px',
                  lg: '96px',
                  xl: '96px',
                },
                fontStyle: 'normal',
                fontWeight: 700,
                lineHeight: 'normal',
                ml: { xs: 2, sm: 4, md: 8 },
              }}
              color='primary'
              data-testid='home-title'
            >
              The Mobility Database
            </Typography>
          </Grid>
          <Grid item sm={12} md={5}>
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
              }}
            >
              The Mobility Database catalogs is a repository of 2000+ mobility
              feeds across the world. It has over 150 updated feeds previously
              unavailable on TransitFeeds (OpenMobilityData).
              <br />
              <br />
              We’re in the first phase of building a sustainable, central hub
              for mobility data internationally.
            </Box>
          </Grid>
        </Grid>
        <Typography
          component='h1'
          variant='h5'
          sx={{ textAlign: 'center', color: 'black', fontWeight: 700, mt: 5 }}
        >
          Currently serving data from over{' '}
          <span style={{ color: '#3859FA' }}>2000</span> GTFS feeds in{' '}
          <span style={{ color: '#3859FA' }}>70</span> countries.
        </Typography>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
          }}
        >
          <Button variant='contained' sx={{ m: 2 }} startIcon={<Download />}>
            <a
              href='https://bit.ly/catalogs-csv'
              target='_blank'
              className='btn-link'
              rel='noreferrer'
            >
              Download the entire catalog
            </a>
          </Button>
          <Button variant='contained' sx={{ m: 2 }} startIcon={<Login />}>
            <a href='/sign-up' className='btn-link' rel='noreferrer'>
              Sign up for the API
            </a>
          </Button>
        </Box>
      </Box>
      <Box
        sx={{
          width: '100vw',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          justifyItems: 'center',
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
          <Typography variant='h5' sx={{ fontWeight: 700 }}>
            What About TransitFeeds?
          </Typography>
          You’ll be able to access transitfeeds.com until a deprecation date is
          decided
          <br />
          <Typography>
            The data on TransitFeeds is becoming increasingly out of date and
            cannot be updated, which is negatively impacting travelers. That’s
            why we’re encouraging users to use the Mobility Database instead,
            which they can actively contribute to and improve.
            <br />
            <br />
            We will discuss the transition process in greater depth before
            committing to a specific date to remove access to transitfeeds.com.
            No decision has been made yet. If you want to participated in a
            discussion about the deprecation of transitfeeds.com, let us know in
            the catalogs GtiHub repo. We commit to giving 6 months notice once
            the decision is finalized.
          </Typography>
        </Box>
      </Box>
    </Container>
  );
}
