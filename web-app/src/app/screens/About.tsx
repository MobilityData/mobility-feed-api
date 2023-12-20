import * as React from 'react';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import '../styles/SignUp.css';
import { Button, Typography } from '@mui/material';
import { OpenInNew } from '@mui/icons-material';

export default function About(): React.ReactElement {
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
        <Typography variant='h4' color='primary' sx={{ fontWeight: 700 }}>
          About{' '}
        </Typography>
        <Box
          sx={{
            background: '#F8F5F5',
            width: '90vw',
            mt: 2,
            p: 2,
            borderRadius: '6px 6px 0px 0px',
          }}
        >
          <Typography sx={{ fontWeight: 700 }}>
            The Mobility Database is hosted and supported by MobilityData, a
            non-profit organization that improves and extends mobility data
            formats, including GTFS, GTFS Realtime and GBFS.
            <br /> <br />
            MobilityData is currently working on the Mobility Database because
            of the need for a sustainable, community-supported hub for
            international mobility datasets.
          </Typography>

          <Typography
            variant='h5'
            color='primary'
            sx={{ fontWeight: 700, mt: 5 }}
          >
            The History
          </Typography>
          <Typography>
            Discoverability is at the heart of mobility: travelers need to know
            the mobility options available and understand their intricacies to
            plan their journey; app creators need simplified access to data to
            relay to app users. Discoverability is the cement of the community
            that MobilityData is building around open data formats (such as GTFS
            and GBFS) and their datasets.
            <br />
            <br />
            A need to improve discoverability gave rise to the TransitFeeds.com
            project, which made it easier to find and query accurate and
            up-to-date GTFS, GTFS Realtime, GBFS, and datasets. This project was
            housed by MobilityData following a transition from ActionFigure
            (formerly TransitScreen).
            <br />
            <br />
            MobilityData created a long-term roadmap for the project, taking
            into account the repeated historic challenges the GTFS repositories
            have encountered and the need to expand to accommodate additional
            modes of transport and data formats.
          </Typography>
          <Typography
            variant='h5'
            color='primary'
            sx={{ fontWeight: 700, mt: 5 }}
          >
            About MobilityData
          </Typography>
          <Typography>
            MobilityData began in 2015 as a Rocky Mountain Institute project and
            became a Canadian non-profit in 2019 with the mission to improve
            traveler information. Building on the strength of nearly 20
            employees, MobilityData brings together and supports mobility
            stakeholders such as transport agencies, software vendors, mobility
            apps, and cities to standardize and expand data formats for public
            transport (GTFS) and shared mobility (GBFS).
          </Typography>
          <Button variant='contained' sx={{ mt: 5 }} endIcon={<OpenInNew />}>
            <a
              href='https://mobilitydata.org/'
              target='_blank'
              className='btn-link'
              rel='noreferrer'
            >
              Learn more about MobilityData
            </a>
          </Button>
        </Box>
      </Box>
    </Container>
  );
}
