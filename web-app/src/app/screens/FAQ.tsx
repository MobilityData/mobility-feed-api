import * as React from 'react';
import Container from '@mui/material/Container';
import { Button, Typography } from '@mui/material';
import { ColoredContainer } from '../styles/PageLayout.style';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';

export default function FAQ(): React.ReactElement {
  return (
    <Container component='main'>
      <Typography variant='h1'>Frequently Asked Questions (FAQ) </Typography>
      <ColoredContainer maxWidth={false} sx={{ mt: 3 }}>
        <Typography
          variant='h5'
          color='primary'
          sx={{ fontWeight: 700, mb: 1 }}
        >
          What is the Mobility Database?
        </Typography>
        <Typography className='answer'>
          The Mobility Database is an open database containing over 4000+
          transit and shared mobility feeds in GTFS, GTFS Realtime, and GBFS
          formats. In addition to our database, we also offer an API, and
          data-quality reports using the Canonical GTFS Validator and the GBFS
          Validator.
          <br /> <br />
          This database is hosted and maintained by MobilityData, the global
          non-profit organization dedicated to the advancement of open
          transportation data standards.
          <br />
          <Button
            component={'a'}
            variant='contained'
            sx={{ mt: 3 }}
            endIcon={<OpenInNewIcon />}
            href='https://mobilitydata.org/'
            rel='noreferrer'
            target='_blank'
          >
            Learn more about MobilityData
          </Button>
        </Typography>
        <Typography
          variant='h5'
          color='primary'
          sx={{ fontWeight: 700, mt: 5, mb: 1 }}
        >
          Who can use the Mobility Database?
        </Typography>
        <Typography className='answer'>
          Everyone has free access to the Mobility Database. However, to&#20;
          <Button
            variant='text'
            className='line-start inline'
            href={'/contribute'}
          >
            add a feed
          </Button>
          or&#20;
          <Button
            variant='text'
            className='line-start inline'
            href={
              'https://mobilitydata.github.io/mobility-feed-api/SwaggerUI/index.html'
            }
          >
            use our API
          </Button>
          you’ll need to&#20;
          <Button
            variant='text'
            className='line-start inline'
            href={'/sign-up'}
          >
            create an account.
          </Button>
        </Typography>
        <Typography
          variant='h5'
          color='primary'
          sx={{ fontWeight: 700, mt: 5, mb: 1 }}
        >
          Does the Mobility Database replace TransitFeeds.com?
        </Typography>
        <Typography className='answer'>
          Yes. The Mobility Database was launched in February of 2024 to replace
          Transitfeeds. Currently, the TransitFeeds website remains accessible,
          acting as a temporary archive for data from 2014 to February of 2024.
          All historical data will be migrated to the Mobility Database before
          deprecation. All data newer than February 2024 can be found in our
          database, including 2500+ feeds not originally available on
          TransitFeeds.
          <br /> <br />
          Likewise, the Mobility Database API replaces the TransitFeeds API to
          provide the most up-to-date GTFS and GTFS-Realtime available. You can
          still use the TransitFeeds API to access historical data; however,
          support will cease when TransitFeeds is officially deprecated.
          <br /> <br />
          <b>Note: TransitFeeds will be deprecated in December 2025. </b>
        </Typography>
        <Typography
          variant='h5'
          color='primary'
          sx={{ fontWeight: 700, mt: 5, mb: 1 }}
        >
          How often is the Mobility Database updated?
        </Typography>
        <Typography className='answer'>
          Every day at midnight UTC, the Mobility Database checks for feed
          updates using the URL provided by the producer upon uploading. If we
          detect a change, we add the new feed version automatically.
          <br /> <br />
          For GBFS feeds, we do an additional sync any time a change to the&#20;
          <Button
            variant='text'
            className='line-start inline'
            href={
              'https://github.com/MobilityData/gbfs/blob/master/systems.csv'
            }
            rel='noreferrer'
            target='_blank'
            endIcon={<OpenInNewIcon />}
          >
            systems.csv catalog
          </Button>
          is merged.
        </Typography>
        <Typography
          variant='h5'
          color='primary'
          sx={{ fontWeight: 700, mt: 5, mb: 1 }}
        >
          I am a transit or shared mobility operator, how can I use the Mobility
          Database?
        </Typography>
        <Typography className='answer'>
          The main benefit is that having your feed in the database ensures more
          rider-facing apps discover and use your data. Plus, the integration
          with the Canonical GTFS Schedule Validator and GBFS validator means
          your GTFS or GBFS feed will be checked before you submit them to a
          trip-planner or navigation application. You’ll receive a detailed
          error quality report, which reduces the amount of back and forth in
          the process and allows you to submit high-quality data to give your
          riders reliable, detailed information. Another benefit of our Database
          is simply the access you have to search, download, and look at other
          feeds to get examples on how to improve your own data, whether it is
          GTFS Schedule, GTFS Realtime, or GBFS.
        </Typography>
        <Typography
          variant='h5'
          color='primary'
          sx={{ fontWeight: 700, mt: 5, mb: 1 }}
        >
          I want to consume/analyze/display transport data, how can I use the
          Mobility Database?
        </Typography>
        <Typography className='answer'>
          Our API allows you to pull data from our database seamlessly. Since
          our URLs are stable and checked for updates on a daily basis, data
          doesn’t get dropped if an agency’s website is down, or if the link
          expires.
          <br /> <br />
          Detailed instructions for installing and implementing our API can be
          found on&#20;
          <Button
            variant='text'
            className='inline line-start'
            href={
              'https://mobilitydata.github.io/mobility-feed-api/SwaggerUI/index.html'
            }
            rel='noreferrer'
            target='_blank'
          >
            Swagger.
          </Button>
          In addition to searching the database or using our API to pull data,
          you’re able to&#20;
          <Button
            variant='text'
            className='inline line-start'
            href={'https://files.mobilitydatabase.org/feeds_v2.csv'}
            rel='noreferrer'
            target='_blank'
            endIcon={<OpenInNewIcon />}
          >
            download GTFS and GTFS Realtime feeds via the spreadsheet here
          </Button>
          <br /> <br />
          GBFS feeds can be downloaded via a spreadsheet with the&#20;
          <Button
            variant='text'
            className='line-start inline'
            href={
              'https://github.com/MobilityData/gbfs?tab=readme-ov-file#systems-catalog---systems-implementing-gbfs'
            }
            rel='noreferrer'
            target='_blank'
            endIcon={<OpenInNewIcon />}
          >
            systems.csv catalog
          </Button>
        </Typography>
      </ColoredContainer>
    </Container>
  );
}
