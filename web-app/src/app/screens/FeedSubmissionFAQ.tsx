import * as React from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  type SxProps,
  Typography,
  Box,
  Container,
  CssBaseline,
  useTheme,
  Button,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import FileDownloadIcon from '@mui/icons-material/FileDownload';

export default function FeedSubmissionFAQ(): React.ReactElement {
  const theme = useTheme();

  const accordionStyle: SxProps = {
    boxShadow: 'none',
    background: 'transparent',
    borderBottom: '2px solid',
    borderColor: theme.palette.divider,
    '&:before': { display: 'none' },
    svg: { color: theme.palette.divider },
  };

  return (
    <Container component='main' sx={{ my: 0, mx: 'auto' }}>
      <CssBaseline />
      <Typography
        component='h1'
        variant='h4'
        color='primary'
        sx={{ fontWeight: 700 }}
      >
        Frequently Asked Questions about Adding Feeds
      </Typography>
      <Box
        sx={{
          background: theme.palette.background.paper,
          mt: 2,
          p: 2,
          borderRadius: '6px 6px 0px 0px',
        }}
      >
        <Accordion sx={accordionStyle}>
          <AccordionSummary
            aria-controls='panel1-content'
            id='panel1-header'
            expandIcon={<ExpandMoreIcon />}
          >
            <Typography sx={{ fontWeight: 'bold' }}>
              Can I contribute GBFS feeds?
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography>
              If you want to add GBFS feeds to the Mobility Database, please
              contribute to
              <Button
                variant='text'
                className='inline'
                href={
                  'https://github.com/MobilityData/gbfs?tab=readme-ov-file#systems-catalog---systems-implementing-gbfs'
                }
                rel='noreferrer'
                target='_blank'
                endIcon={<OpenInNewIcon />}
              >
                the GBFS systems.csv catalog.
              </Button>
              The Mobility Database automatically syncs with systems.csv.
            </Typography>
          </AccordionDetails>
        </Accordion>
        <Accordion sx={accordionStyle}>
          <AccordionSummary
            aria-controls='panel1-content'
            id='panel1-header'
            expandIcon={<ExpandMoreIcon />}
          >
            <Typography sx={{ fontWeight: 'bold' }}>
              What is a GTFS feed?
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography>
              A GTFS feed is a downloadable set of files that adhere to the
              <Button
                variant='text'
                className='inline'
                href={'https://gtfs.org/'}
                rel='noreferrer'
                target='_blank'
                endIcon={<OpenInNewIcon />}
              >
                General Transit Feed Specification
              </Button>
              .
              <br />
              <br />A GTFS Schedule feed that includes static information about
              a transit service is a collection of text (.txt) files that are
              contained in a single ZIP file. A GTFS Realtime feed that provides
              realtime updates to riders is formatted as
              <Button
                variant='text'
                className='inline'
                href={'https://protobuf.dev/'}
                rel='noreferrer'
                target='_blank'
                endIcon={<OpenInNewIcon />}
              >
                Protocol Buffer data
              </Button>
              and shared as a proto file. A GTFS Realtime feed can include a mix
              of Trip Updates, Vehicle Positions, and Service Alerts or there
              can be separate feeds for each type of realtime information.
              <br />
              <br />
              Each direct download URL for a GTFS feed has to open a file. For
              example, a URL that points to an agency&apos;s GTFS explainer page
              such as
              <Button
                variant='text'
                className='inline'
                href={'https://www.bctransit.com/open-data'}
                rel='noreferrer'
                target='_blank'
              >
                https://www.bctransit.com/open-data
              </Button>
              is not a valid GTFS feed URL. However,
              <Button
                variant='text'
                className='inline'
                href={'https://www.bctransit.com/data/gtfs/powell-river.zip'}
                rel='noreferrer'
                target='_blank'
              >
                https://www.bctransit.com/data/gtfs/powell-river.zip
              </Button>
              is a valid GTFS feed download link because it directly opens the
              GTFS feed. The same principle is used for GTFS feeds that are
              accessible via an API: a generic link to the API, such as
              <Button
                variant='text'
                className='inline'
                href={'http://api.511.org/transit/datafeeds'}
                rel='noreferrer'
                target='_blank'
              >
                http://api.511.org/transit/datafeeds
              </Button>
              , is invalid. A valid download URL would need to include an API
              query that returns a GTFS feed, such as
              <Button
                variant='text'
                className='inline'
                href={'http://api.511.org/transit/datafeeds?operator_id=3D'}
                rel='noreferrer'
                target='_blank'
              >
                http://api.511.org/transit/datafeeds?operator_id=3D
              </Button>
              .
            </Typography>
          </AccordionDetails>
        </Accordion>

        <Accordion sx={accordionStyle}>
          <AccordionSummary
            aria-controls='panel2-content'
            id='panel2-header'
            expandIcon={<ExpandMoreIcon />}
          >
            <Typography sx={{ fontWeight: 'bold' }}>
              Why would I want to add or update a feed?
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography>
              Adding a feed means that more journey planning apps can discover
              the data and share it with travelers. Service planning tools and
              researchers also rely on data aggregators like the Mobility
              Database catalogs to evaluate services and plan future ones.
              <br />
              <br />
              To ensure that travelers have access to the most up-to-date
              information, transit providers should add a new feed on the
              catalogs when their feed URL changes. Transit providers should
              review
              <Button
                variant='text'
                className='inline'
                href={
                  'https://storage.googleapis.com/storage/v1/b/mdb-csv/o/sources.csv?alt=media'
                }
                endIcon={<FileDownloadIcon />}
              >
                the spreadsheet of feeds already in the Mobility Database
              </Button>
              to see if an old URL of their feed is in the Mobility Database and
              request that its status be set to deprecated under Issue Type in
              the form below.
              <br />
              <br />
              <b>Deprecated</b> is a manually set status within the Mobility
              Database that indicates that a feed has been replaced with a new
              URL. MobilityData staff will deprecate the old feed and set a{' '}
              <b>redirect</b> to indicate that the new feed should be used
              instead of the deprecated one.
              <br />
              <br />
              If transit providers would like to share old feed URLs for
              researchers and analysts to use, please add the feed to the form
              below and request that its status be set to deprecated.
            </Typography>
          </AccordionDetails>
        </Accordion>

        <Accordion sx={accordionStyle}>
          <AccordionSummary
            aria-controls='panel3-content'
            id='panel3-header'
            expandIcon={<ExpandMoreIcon />}
          >
            <Typography sx={{ fontWeight: 'bold' }}>
              When should I contribute a feed?
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography>
              To ensure that travelers have access to the most up-to-date
              information, transit providers should add a new feed on the
              catalogs when there are major changes to their URL. Examples of
              changes include:
            </Typography>
            <Box component='ul' sx={{ typography: 'body1' }}>
              <li>The feed URL changes</li>
              <li>
                The feed is combined with several other feeds (for example:
                several providers&apos; feeds are combined together)
              </li>
              <li>
                The feed is split from a combined/aggregated feed (for example:
                a provider whose GTFS was only available in an aggregate feed
                now has their own independent feed)
              </li>
            </Box>
          </AccordionDetails>
        </Accordion>

        <Accordion sx={accordionStyle}>
          <AccordionSummary
            aria-controls='panel4-content'
            id='panel4-header'
            expandIcon={<ExpandMoreIcon />}
          >
            <Typography sx={{ fontWeight: 'bold' }}>
              Who can contribute a feed?
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography>
              Anyone can add or update a feed, and it is currently merged
              manually into the catalogs by the MobilityData team. The name of
              the person requesting the feed is captured in the PR, either via
              their GitHub profile or based on the information shared in the
              form below.
              <br />
              <br />
              In order to verify the validity of a GTFS schedule source, an
              automated test is also run to check if the direct download URL
              provided opens a functional ZIP file.
            </Typography>
          </AccordionDetails>
        </Accordion>

        <Accordion sx={accordionStyle}>
          <AccordionSummary
            aria-controls='panel5-content'
            id='panel5-header'
            expandIcon={<ExpandMoreIcon />}
          >
            <Typography sx={{ fontWeight: 'bold' }}>
              How do I contribute a feed?
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography>
              There are two ways to update a feed:
              <br />
              <br />
              <span style={{ fontWeight: 700 }}>
                1. If you&apos;re not comfortable with GitHub or only have a few
                feeds to add:
              </span>{' '}
              use the form below to request a feed change. The feed will be
              added as a pull request in GitHub viewable to the public within a
              week of being submitted. You can verify the change has been made
              to the catalogs by reviewing this CSV file. In the future, this
              process will be automated so the PR is automatically created once
              submitted and merged when tests pass.
              <br />
              <br />
              <span style={{ fontWeight: 700 }}>
                2. If you want to add feeds directly:
              </span>{' '}
              you can follow
              <Button
                variant='text'
                className='inline'
                href={
                  'https://github.com/MobilityData/mobility-database-catalogs/blob/main/CONTRIBUTING.md'
                }
                rel='noreferrer'
                target='_blank'
                endIcon={<OpenInNewIcon />}
              >
                the CONTRIBUTING.MD file
              </Button>
              in GitHub to add sources.
              <br />
              <br />
              If you have any questions or concerns about this process, you can
              email
              <Button
                variant='text'
                className='inline'
                href={'mailto:api@mobilitydata.org'}
                rel='noreferrer'
                target='_blank'
              >
                api@mobilitydata.org
              </Button>
              for support in getting your feed added.
            </Typography>
          </AccordionDetails>
        </Accordion>

        <Accordion sx={accordionStyle}>
          <AccordionSummary
            aria-controls='panel6-content'
            id='panel6-header'
            expandIcon={<ExpandMoreIcon />}
          >
            <Typography sx={{ fontWeight: 'bold' }}>
              What if I want to remove a feed?
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography>
              Feeds are only removed in instances when it is requested by the
              producer of the data because of licensing issues. In all other
              cases, feeds are set to a status of deprecated so it&apos;s
              possible to include their historical data within the Mobility
              Database.
            </Typography>
          </AccordionDetails>
        </Accordion>

        <Accordion sx={accordionStyle}>
          <AccordionSummary
            aria-controls='panel7-content'
            id='panel7-header'
            expandIcon={<ExpandMoreIcon />}
          >
            <Typography sx={{ fontWeight: 'bold' }}>
              Shoutout to our incredible contributors
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography>
              🎉 Thanks to all those who have contributed. This includes any
              organizations or unaffiliated individuals who have added data,
              updated data, or contributed code since 2021.
              <br />
              <br />
              <b>Organizations:</b>
            </Typography>
            <Box component='ul' sx={{ typography: 'body1' }}>
              <li>Adelaide Metro</li>
              <li>Bettendorf Transit</li>
              <li>Bi-State Regional Commission</li>
              <li>BreizhGo</li>
              <li>Cal-ITP</li>
              <li>Commerce Municipal Bus Lines</li>
              <li>Corpus Christi Regional Transportation Authority</li>
              <li>County of Hawai&apos;i Mass Transit Agency</li>
              <li>DART Delaware</li>
              <li>
                Department of Municipalities and Transport, Abu Dhabi, United
                Arab Emirates
              </li>
              <li>Development Bank of Latin America (CAF)</li>
              <li>Digital Transport for Africa (DT4A)</li>
              <li>ECO Transit</li>
              <li>Eismo Info</li>
              <li>Entur AS</li>
              <li>GTFS.be</li>
              <li>Garnet Consultants</li>
              <li>Golden Gate Bridge Highway Transit District</li>
              <li>High Valley Transit</li>
              <li>Kitsap Transit</li>
              <li>Kuzzle</li>
              <li>Metro Christchurch</li>
              <li>Metro de Málaga</li>
              <li>Passio Technologies</li>
              <li>Pinpoint AVL</li>
              <li>Port Phillip Ferries</li>
              <li>Redmon Group</li>
              <li>Rhode Island Public Transit Authority (RIPTA)</li>
              <li>Rio de Janeiro City Hall</li>
              <li>Rochester-Genesee Regional Transportation Authority</li>
              <li>Roma Mobilita</li>
              <li>SFMTA</li>
              <li>SMMAG</li>
              <li>San Francisco Municipal Transportation Agency (SFMTA)</li>
              <li>San Luis Obispo Regional Transit Authority</li>
              <li>Santiago Directorio de Transporte Público Metropolitano</li>
              <li>Skedgo</li>
              <li>Société nationale des chemins de fer français (SNCF)</li>
              <li>Sound Transit</li>
              <li>Springfield Mass Transit District (SMTD)</li>
              <li>Ticpoi</li>
              <li>Transcollines</li>
              <li>Transport for Cairo</li>
              <li>Two Sigma Data Clinic</li>
              <li>UCSC Transporation and Parking Services</li>
              <li>Unobus</li>
              <li>Volánbusz</li>
              <li>Walker Consultants</li>
            </Box>
            <Typography>
              <b>Individuals:</b> <br />
              If you are listed here and would like to add your organization,
              <Button
                variant='text'
                className='inline'
                href={'mailto:api@mobilitydata.org'}
                rel='noreferrer'
                target='_blank'
              >
                let MobilityData know
              </Button>
              .
            </Typography>
            <Box component='ul' sx={{ typography: 'body1' }}>
              <li>@1-Byte on GitHub</li>
              <li>Allan Fernando</li>
              <li>Eloi Torrents</li>
              <li>Florian Maunier</li>
              <li>Gábor Kovács</li>
              <li>Jessica Rapson</li>
              <li>Joop Kiefte</li>
              <li>Justin Brooks</li>
              <li>Kevin Butler</li>
              <li>Kovács Áron</li>
              <li>Oliver Hattshire</li>
              <li>Saipraneeth Devunuri</li>
            </Box>
          </AccordionDetails>
        </Accordion>
      </Box>
    </Container>
  );
}
