import { Container, Typography, Button } from '@mui/material';
// import { ColoredContainer } from '../styles/PageLayout.style';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';

export default function Page() {
  return (
    <Container component='main'>
      {/* <ColoredContainer maxWidth={false} sx={{ mt: 3 }}> */}
      <Typography variant='h1'>About</Typography>
      <Container>
        <Typography sx={{ fontWeight: 700 }}>
          The Mobility Database is an open catalog including over 4000 GTFS,
          GTFS Realtime, and GBFS feeds in over 75 countries. It integrates with
          the Canonical GTFS Schedule and GBFS Validators to share data quality
          reports for each feed.
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
          Why Use the Mobility Database?
        </Typography>
        <Typography className='answer'>
          The Mobility Database provides free access to historical and current
          GTFS, GTFS Realtime, and GBFS feeds from around the world. These feeds
          are checked for updates every day, ensuring that the data you’re
          looking at is the most recent data available.
          <br /> <br />
          In addition to our database, we develop and maintain other tools that
          integrate with it such as&#20;
          <Button
            variant='text'
            className='line-start inline'
            href={'https://gtfs-validator.mobilitydata.org/'}
            rel='noreferrer'
            target='_blank'
            endIcon={<OpenInNewIcon />}
          >
            the Canonical GTFS Schedule Validator
          </Button>
          and&#20;
          <Button
            variant='text'
            className='line-start inline'
            href={'https://gbfs-validator.mobilitydata.org/'}
            rel='noreferrer'
            target='_blank'
            endIcon={<OpenInNewIcon />}
          >
            the GBFS Validator.
          </Button>
          Additional benefits of using the Mobility Database include
          <ul>
            <li>
              Mirrored versions of operator-hosted GTFS Schedule feeds to avoid
              operator website downtimes and geoblocking
            </li>
            <li>
              Bounding boxes that help to visualize or filter in the API by a
              select region
            </li>
            <li>
              <Button
                variant='text'
                className='line-start inline'
                href={'/contribute'}
                rel='noreferrer'
                target='_blank'
              >
                A simple, easy-to-use form to add new feeds
              </Button>
            </li>
            <li>
              An open source community actively working to improve the tools
            </li>
          </ul>
        </Typography>
      </Container>
    </Container>
  );
}
