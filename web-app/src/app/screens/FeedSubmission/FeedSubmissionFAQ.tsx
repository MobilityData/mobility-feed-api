/* eslint-disable react/no-unescaped-entities */
import * as React from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Typography,
  colors,
} from '@mui/material';

export default function FeedSubmissionFAQ(): React.ReactElement {
  return (
    <>
      <Typography
        sx={{
          color: colors.blue.A700,
          fontWeight: 'bold',
          fontSize: { xs: 18, sm: 24 },
        }}
      >
        Frequently Asked Questions about Adding Feeds
      </Typography>
      <Accordion>
        <AccordionSummary aria-controls='panel1-content' id='panel1-header'>
          <Typography>What is a GTFS feed?</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Typography>
            A GTFS feed is a downloadable set of files that adhere to the{' '}
            <a href='https://gtfs.org/' target='_blank' rel='noreferrer'>
              General Transit Feed Specification
            </a>
            .
            <br />
            <br />A GTFS Schedule feed that includes static information about a
            transit service is a collection of text (.txt) files that are
            contained in a single ZIP file. A GTFS Realtime feed that provides
            realtime updates to riders is formatted as{' '}
            <a href='https://protobuf.dev/' target='_blank' rel='noreferrer'>
              Protocol Buffer data
            </a>{' '}
            and shared as a proto file. A GTFS Realtime feed can include a mix
            of Trip Updates, Vehicle Positions, and Service Alerts or there can
            be separate feeds for each type of realtime information.
            <br />
            <br />
            Each direct download URL for a GTFS feed has to open a file. For
            example, a URL that points to an agency's GTFS explainer page such
            as{' '}
            <a
              href='https://www.bctransit.com/open-data'
              target='_blank'
              rel='noreferrer'
            >
              https://www.bctransit.com/open-data
            </a>{' '}
            is not a valid GTFS feed URL. However,{' '}
            <a
              href='https://www.bctransit.com/data/gtfs/powell-river.zip'
              target='_blank'
              rel='noreferrer'
            >
              https://www.bctransit.com/data/gtfs/powell-river.zip
            </a>{' '}
            is a valid GTFS feed download link because it directly opens the
            GTFS feed. The same principle is used for GTFS feeds that are
            accessible via an API: a generic link to the API, such as{' '}
            <a
              href='http://api.511.org/transit/datafeeds'
              target='_blank'
              rel='noreferrer'
            >
              http://api.511.org/transit/datafeeds
            </a>
            , is invalid. A valid download URL would need to include an API
            query that returns a GTFS feed, such as{' '}
            <a
              href='http://api.511.org/transit/datafeeds?operator_id=3D'
              target='_blank'
              rel='noreferrer'
            >
              http://api.511.org/transit/datafeeds?operator_id=3D
            </a>
            .
          </Typography>
        </AccordionDetails>
      </Accordion>

      <Accordion>
        <AccordionSummary aria-controls='panel2-content' id='panel2-header'>
          <Typography>Why would I want to add or update a feed?</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Typography>
            Adding a feed means that more journey planning apps can discover the
            data and share it with travelers. Service planning tools and
            researchers also rely on data aggregators like the Mobility Database
            catalogs to evaluate services and plan future ones.
            <br />
            <br />
            To ensure that travelers have access to the most up-to-date
            information, transit providers should add a new feed on the catalogs
            when their feed URL changes. Transit providers should review{' '}
            <a
              href='https://bit.ly/catalogs-csv'
              target='_blank'
              rel='noreferrer'
            >
              the spreadsheet of feeds already in the Mobility Database
            </a>{' '}
            to see if an old URL of their feed is in the Mobility Database and
            request that its status be set to deprecated under Issue Type in the
            form below.
            <br />
            <br />
            <b>Deprecated</b> is a manually set status within the Mobility
            Database that indicates that a feed has been replaced with a new
            URL. MobilityData staff will deprecate the old feed and set a{' '}
            <b>redirect</b> to indicate that the new feed should be used instead
            of the deprecated one.
            <br />
            <br />
            If transit providers would like to share old feed URLs for
            researchers and analysts to use, please add the feed to the form
            below and request that its status be set to deprecated.
          </Typography>
        </AccordionDetails>
      </Accordion>

      <Accordion>
        <AccordionSummary aria-controls='panel3-content' id='panel3-header'>
          <Typography>When should I contribute a feed?</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Typography>
            To ensure that travelers have access to the most up-to-date
            information, transit providers should add a new feed on the catalogs
            when there are major changes to their URL. Examples of changes
            include:
            <ul>
              <li>The feed URL changes</li>
              <li>
                The feed is combined with several other feeds (for example:
                several providers' feeds are combined together)
              </li>
              <li>
                The feed is split from a combined/aggregated feed (for example:
                a provider whose GTFS was only available in an aggregate feed
                now has their own independent feed)
              </li>
            </ul>
          </Typography>
        </AccordionDetails>
      </Accordion>

      <Accordion>
        <AccordionSummary aria-controls='panel4-content' id='panel4-header'>
          <Typography>Who can contribute a feed?</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Typography>
            Anyone can add or update a feed, and it is currently merged manually
            into the catalogs by the MobilityData team. The name of the person
            requesting the feed is captured in the PR, either via their GitHub
            profile or based on the information shared in the form below.
            <br />
            <br />
            In order to verify the validity of a GTFS schedule source, an
            automated test is also run to check if the direct download URL
            provided opens a functional ZIP file.
          </Typography>
        </AccordionDetails>
      </Accordion>

      <Accordion>
        <AccordionSummary aria-controls='panel5-content' id='panel5-header'>
          <Typography>How do I contribute a feed?</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Typography>
            There are two ways to update a feed:
            <br />
            <br />
            <span style={{ fontWeight: 700 }}>
              1. If you're not comfortable with GitHub or only have a few feeds
              to add:
            </span>{' '}
            use the form below to request a feed change. The feed will be added
            as a pull request in GitHub viewable to the public within a week of
            being submitted. You can verify the change has been made to the
            catalogs by reviewing this CSV file. In the future, this process
            will be automated so the PR is automatically created once submitted
            and merged when tests pass.
            <br />
            <br />
            <span style={{ fontWeight: 700 }}>
              2. If you want to add feeds directly:
            </span>{' '}
            you can follow{' '}
            <a
              href='https://github.com/MobilityData/mobility-database-catalogs/blob/main/CONTRIBUTING.md'
              target='_blank'
              rel='noreferrer'
            >
              the CONTRIBUTING.MD file
            </a>{' '}
            in GitHub to add sources.
            <br />
            <br />
            If you have any questions or concerns about this process, you can
            email{' '}
            <a
              href='mailto:api@mobilitydata.org'
              target='_blank'
              rel='noreferrer'
            >
              api@mobilitydata.org
            </a>{' '}
            for support in getting your feed added.
          </Typography>
        </AccordionDetails>
      </Accordion>

      <Accordion>
        <AccordionSummary aria-controls='panel6-content' id='panel6-header'>
          <Typography>What if I want to remove a feed?</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Typography>
            Feeds are only removed in instances when it is requested by the
            producer of the data because of licensing issues. In all other
            cases, feeds are set to a status of deprecated so it's possible to
            include their historical data within the Mobility Database.
          </Typography>
        </AccordionDetails>
      </Accordion>

      <Accordion>
        <AccordionSummary aria-controls='panel7-content' id='panel7-header'>
          <Typography>Shoutout to our incredible contributors</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Typography>
            🎉 Thanks to all those who have contributed. This includes any
            organizations or unaffiliated individuals who have added data,
            updated data, or contributed code since 2021.
            <br />
            <br />
            <b>Organizations:</b>
            <ul style={{ marginTop: 0 }}>
              <li>Adelaide Metro</li>
              <li>Bettendorf Transit</li>
              <li>Bi-State Regional Commission</li>
              <li>BreizhGo</li>
              <li>Cal-ITP</li>
              <li>Commerce Municipal Bus Lines</li>
              <li>Corpus Christi Regional Transportation Authority</li>
              <li>County of Hawai'i Mass Transit Agency</li>
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
            </ul>
            <br />
            <br />
            <b>Individuals:</b> <br />
            If you are listed here and would like to add your organization,{' '}
            <a
              href='mailto:api@mobilitydata.org'
              target='_blank'
              rel='noreferrer'
            >
              let MobilityData know
            </a>
            .
            <ul style={{ marginTop: 0 }}>
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
            </ul>
          </Typography>
        </AccordionDetails>
      </Accordion>
    </>
  );
}
