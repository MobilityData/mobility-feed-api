import * as React from 'react';
import Container from '@mui/material/Container';
import { Button, Typography } from '@mui/material';
import { WEB_VALIDATOR_LINK } from '../constants/Navigation';
import { MainPageHeader } from '../styles/PageHeader.style';
import { ColoredContainer } from '../styles/PageLayout.style';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import FileDownloadIcon from '@mui/icons-material/FileDownload';

export default function FAQ(): React.ReactElement {
  return (
    <Container component='main'>
      <MainPageHeader>Frequently Asked Questions (FAQ) </MainPageHeader>
      <ColoredContainer maxWidth={false} sx={{ mt: 3 }}>
        <Typography
          variant='h5'
          color='primary'
          sx={{ fontWeight: 700, mb: 1 }}
        >
          Why use the Mobility Database?
        </Typography>
        <Typography className='answer'>
          The Mobility Database is a catalog that makes it easy to find over
          2,000 GTFS and GTFS Realtime feeds, including more accurate and newer
          feeds not found on TransitFeeds. The Mobility Database integrates with
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
          to provide data quality insights.
        </Typography>
        <Typography
          variant='h5'
          color='primary'
          sx={{ fontWeight: 700, mt: 5, mb: 1 }}
        >
          How do I use the Mobility Database?
        </Typography>
        <Typography className='answer'>
          There are 3 ways to use the Mobility Database:
          <br />
          <br />
          1. The feed search on the website, where you can discover feeds and
          see details on their bounding box, data quality, and historical data.
          <br />
          2. The API, where you can pull feed information to display in your own
          application or for research analysis
          <br />
          3. The
          <Button
            variant='text'
            className='inline'
            href={'https://bit.ly/catalogs-csv'}
            endIcon={<FileDownloadIcon />}
          >
            spreadsheet export available here
          </Button>
          . You can find
          <Button
            variant='text'
            className='inline'
            href={
              'https://github.com/MobilityData/mobility-database-catalogs?tab=readme-ov-file#schemas'
            }
            rel='noreferrer'
            target='_blank'
            endIcon={<OpenInNewIcon />}
          >
            the GTFS Schedule and Realtime schemas for the spreadsheet here
          </Button>
          .
        </Typography>
        <Typography
          variant='h5'
          color='primary'
          sx={{ fontWeight: 700, mt: 5, mb: 1 }}
        >
          Why are you making this change?
        </Typography>
        <Typography className='answer'>
          The mobility community has created several hubs for international GTFS
          feeds over the years (including the GTFS Data Exchange and legacy
          TransitFeeds site). There have been consistent issues with sustaining
          these platforms in the long term, and creating community processes so
          it&apos;s clear how decisions are made and how stakeholders across the
          mobility industry can contribute to the platform.
          <br /> <br />
          That&apos;s the need we&apos;re working to meet with the Mobility
          Database, so more stakeholders can trust the longevity of this
          platform and it can become an increasingly valuable source for
          creating and improving mobility data as a community.
          <br /> <br />
          As TransitFeeds becomes increasingly stale and difficult to maintain,
          it becomes more critical that the consumers have up-to-date data to
          share with travelers and make planning decisions. The catalogs will be
          a starting point for providing up-to-date data the community can
          easily leverage and contribute to while we explore longer term
          solutions for the architecture that require more community investment.
        </Typography>
        <Typography
          variant='h5'
          color='primary'
          sx={{ fontWeight: 700, mt: 5, mb: 1 }}
        >
          What about TransitFeeds?
        </Typography>
        <Typography className='answer'>
          TransitFeeds.com is still available to access historical data before
          February 2024 and see feed visualizations. It will be deprecated once
          both these features are available on the Mobility Database. We commit
          to giving 6 months notice once the decision is finalized.
          <br /> <br />
          How quickly we scale the architecture to add these features depends on
          how much engagement and contribution we get from the community in this
          phase.
        </Typography>
        <Typography
          variant='h5'
          color='primary'
          sx={{ fontWeight: 700, mt: 5, mb: 1 }}
        >
          What about the TransitFeeds API?
        </Typography>
        <Typography className='answer'>
          You can use
          <Button variant='text' className='inline' href={'/sign-in'}>
            the Mobility Database API
          </Button>
          instead to access up-to-date GTFS and GTFS Realtime data. The API is
          providing historical data from the time of launch (February 2024). If
          you need to access historical data from previous years from the
          TransitFeeds API, you are still able to. Your systems will be
          unaffected until the to-be-determined deprecation date, when the
          TransitFeeds API will no longer be available.
        </Typography>
        <Typography
          variant='h5'
          color='primary'
          sx={{ fontWeight: 700, mt: 5, mb: 1 }}
        >
          What’s coming next?
        </Typography>
        <Typography className='answer'>
          The MobilityData team is working to add historical data and route and
          stop visualizations to the Mobility Database.
          <br /> <br />
          <Button
            variant='text'
            className='inline line-start'
            href={'https://mobilitydata.org/roadmaps/'}
            rel='noreferrer'
            target='_blank'
            endIcon={<OpenInNewIcon />}
          >
            You can add ideas and vote on our current roadmap
          </Button>
          . We anticipate an influx of new feedback as we transition away from
          TransitFeeds and intend to adapt our plan to the emerging needs of the
          community. How quickly we scale the Mobility Database architecture
          depends on how much engagement and contribution we get from the
          community in this phase.
        </Typography>
        <Typography
          variant='h5'
          color='primary'
          sx={{ fontWeight: 700, mt: 5, mb: 1 }}
        >
          How often do you check for feed updates?
        </Typography>
        <Typography className='answer'>
          The Mobility Database checks for feed updates once a day at midnight
          UTC using the producer&apos;s URL. We store the new feed version if we
          detect a change.
        </Typography>
      </ColoredContainer>
    </Container>
  );
}
