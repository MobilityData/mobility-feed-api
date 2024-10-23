import * as React from 'react';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import '../styles/SignUp.css';
import '../styles/FAQ.css';
import { Typography } from '@mui/material';
import { WEB_VALIDATOR_LINK } from '../constants/Navigation';

export default function FAQ(): React.ReactElement {
  return (
    <Container component='main'>
      <CssBaseline />
      <Box
        sx={{
          mt: 12,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Typography variant='h4' color='primary' sx={{ fontWeight: 700 }}>
          Frequently Asked Questions (FAQ){' '}
        </Typography>
        <Box
          sx={{
            background: '#F8F5F5',
            mt: 2,
            p: 2,
            borderRadius: '6px 6px 0px 0px',
          }}
        >
          <Typography className='question'>
            Why use the Mobility Database?
          </Typography>
          <Typography className='answer'>
            The Mobility Database is a catalog that makes it easy to find over
            2,000 GTFS and GTFS Realtime feeds, including more accurate and
            newer feeds not found on TransitFeeds. The Mobility Database
            integrates with{' '}
            <a href={WEB_VALIDATOR_LINK} target='_blank' rel='noreferrer'>
              the Canonical GTFS Schedule Validator
            </a>{' '}
            to provide data quality insights.
          </Typography>
          <Typography className='question'>
            How do I use the Mobility Database?
          </Typography>
          <Typography className='answer'>
            There are 3 ways to use the Mobility Database:
            <br />
            <br />
            1. The feed search on the website, where you can discover feeds and
            see details on their bounding box, data quality, and historical
            data.
            <br />
            2. The API, where you can pull feed information to display in your
            own application or for research analysis
            <br />
            3. The{' '}
            <a href='https://bit.ly/catalogs-csv'>
              spreadsheet export available here
            </a>
            . You can find{' '}
            <a href='https://github.com/MobilityData/mobility-database-catalogs?tab=readme-ov-file#schemas'>
              the GTFS Schedule and Realtime schemas for the spreadsheet here
            </a>
            .
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
          <Typography className='question'>What about TransitFeeds?</Typography>
          <Typography className='answer'>
            TransitFeeds.com is still available to access historical data before
            February 2024 and see feed visualizations. It will be deprecated
            once both these features are available on the Mobility Database. We
            commit to giving 6 months notice once the decision is finalized.
            <br /> <br />
            How quickly we scale the architecture to add these features depends
            on how much engagement and contribution we get from the community in
            this phase.
          </Typography>
          <Typography className='question'>
            What about the TransitFeeds API?
          </Typography>
          <Typography className='answer'>
            You can use{' '}
            <a href='/sign-in' target='_blank' rel='noreferrer'>
              the Mobility Database API
            </a>{' '}
            instead to access up-to-date GTFS and GTFS Realtime data. The API is
            providing historical data from the time of launch (February 2024).
            If you need to access historical data from previous years from the
            TransitFeeds API, you are still able to. Your systems will be
            unaffected until the to-be-determined deprecation date, when the
            TransitFeeds API will no longer be available.
          </Typography>
          <Typography className='question'>What’s coming next?</Typography>
          <Typography className='answer'>
            The MobilityData team is working to add historical data and route
            and stop visualizations to the Mobility Database.
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
          <Typography className='question'>
            How often do you check for feed updates?
          </Typography>
          <Typography className='answer'>
            The Mobility Database checks for feed updates twice a week using the
            producer&apos;s URL, on Mondays and Thursdays. We store the new feed
            version if we detect a change.
          </Typography>
        </Box>
      </Box>
    </Container>
  );
}
