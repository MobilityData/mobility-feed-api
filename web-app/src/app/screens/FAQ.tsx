import * as React from 'react';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import '../styles/SignUp.css';
import '../styles/FAQ.css';
import { Typography } from '@mui/material';

export default function FAQ(): React.ReactElement {
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
          Frequently Asked Questions (FAQ){' '}
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
          <Typography className='question'>
            Why would I use the Mobility Database?
          </Typography>
          <Typography className='answer'>
            The Mobility Database catalogs has over 100 feeds that were
            inaccurate on TransitFeeds, and over 150 new feeds. It&apos;s a more
            accurate and comprehensive resource for ensuring your data is
            discoverable and for scraping the data you need. The community
            regularly adds and updates feeds using Github.
          </Typography>
          <Typography className='question'>
            Why are you making this change?
          </Typography>
          <Typography className='answer'>
            The mobility community has created several hubs for international
            GTFS feeds over the years (including the GTFS Data Exchange and
            legacy TransitFeeds site). There have been consistent issues with
            sustaining these platforms in the long term, and creating community
            processes so it&apos;s clear how decisions are made and how
            stakeholders across the mobility industry can contribute to the
            platform.
            <br /> <br />
            That&apos;s the need we&apos;re working to meet with the Mobility
            Database, so more stakeholders can trust the longevity of this
            platform and it can become an increasingly valuable source for
            creating and improving mobility data as a community.
            <br /> <br />
            As TransitFeeds becomes increasingly stale and difficult to
            maintain, it becomes more critical that the consumers have
            up-to-date data to share with travelers and make planning decisions.
            The catalogs will be a starting point for providing up-to-date data
            the community can easily leverage and contribute to while we explore
            longer term solutions for the architecture that require more
            community investment.
          </Typography>
           <Typography className='question'>
            What about the TransitFeeds user interface?
          </Typography>
          <Typography className='answer'>
            We plan to develop a new user interface as part of the Mobility
            Database by summer 2024, since this is critical for making data
            discoverable and fostering collaboration on data quality
            improvements.
            <br /> <br />
            In order to ensure the community has access to more up-to-date data
            as soon as possible, we&apos;ve focused on providing a catalog of
            data without an interface as a first step. How quickly we scale the
            architecture to build the user interface depends on how much
            engagement and contribution we get from the community in this phase.
          </Typography>
          <Typography className='question'>
            What about the TransitFeeds API?
          </Typography>
          <Typography className='answer'>
            You can use <a
              href='/sign-in'
              target='_blank'
              rel='noreferrer'
            >the Mobility Database API</a> instead to access up-to-date
            GTFS and GTFS Realtime data. The API is providing historical data from the time of launch (February 2024). If you need to access historical data
            from previous years from the TransitFeeds API, you are still able to. Your systems will
            be unaffected until the to-be-determined deprecation date, when the
            TransitFeeds API will no longer be available. MobilityData will
            migrate the historical data from TransitFeeds to the Mobility
            Database before deprecating the old API.
          </Typography>
          <Typography className='question'>What’s coming next?</Typography>
          <Typography className='answer'>
            The MobilityData team is working to add validation info from the{' '}
            <a
              href='https://gtfs-validator.mobilitydata.org/'
              target='_blank'
              rel='noreferrer'
            >
              Canonical GTFS Schedule Validator
            </a>{' '}
            for each feed, and create a user interface.
            <br /> <br />
            <a
              href='https://mobilitydata.org/roadmaps/'
              target='_blank'
              rel='noreferrer'
            >
              You can add ideas and vote on our current roadmap
            </a>
            . We anticipate an influx of new feedback as we transition away from
            TransitFeeds and intend to adapt our plan to the emerging needs of
            the community. How quickly we scale the Mobility Database
            architecture depends on how much engagement and contribution we get
            from the community in this phase.
          </Typography>
        </Box>
      </Box>
    </Container>
  );
}
