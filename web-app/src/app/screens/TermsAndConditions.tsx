import React from 'react';
import { Box, Button, Container, Typography, useTheme } from '@mui/material';
import CssBaseline from '@mui/material/CssBaseline';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';

export default function TermsAndConditions(): React.ReactElement {
  const theme = useTheme();
  return (
    <Container component='main' sx={{ width: '100%', m: 'auto' }}>
      <CssBaseline />
      <Box
        sx={{
          p: 10,
          pt: 2,
          display: 'flex',
          flexDirection: 'column',
          width: '100%',
          background: theme.palette.background.paper,
        }}
      >
        <Typography
          component='h1'
          variant='h4'
          color='primary'
          sx={{ fontWeight: 700, pb: 4 }}
        >
          Mobility Database API Terms and Conditions
        </Typography>
        <Typography sx={{ fontWeight: 700 }}>1. Acceptance of Terms</Typography>
        <Typography>
          By accessing or using the Mobility Database API, you agree to comply
          with and be bound by the following Terms of Service.
        </Typography>
        <br />
        <Typography sx={{ fontWeight: 700 }}>2. License Information</Typography>
        <Typography>
          <ul style={{ marginTop: 0 }}>
            <li>
              API Codebase License: The API codebase is licensed under the
              <Button
                variant='text'
                href={'https://www.apache.org/licenses/LICENSE-2.0'}
                target={'_blank'}
                rel={'noreferrer'}
                endIcon={<OpenInNewIcon />}
              >
                Apache License 2.0
              </Button>
              .
            </li>
            <li>
              Metadata License: All metadata generated by MobilityData is
              licensed under
              <Button
                variant='text'
                href={
                  'https://creativecommons.org/publicdomain/zero/1.0/legalcode'
                }
                target={'_blank'}
                rel={'noreferrer'}
                endIcon={<OpenInNewIcon />}
              >
                CC0 1.0 Universal (CC0 1.0) Public Domain Dedication.
              </Button>
            </li>
            <li>
              Licenses for the contents of individual feeds: Content within the
              feeds is licensed by their respective data owners. API users are
              responsible for adhering to the licensing terms set by individual
              feed owners. API users are solely responsible for ensuring
              compliance with the licensing requirements for each feed they
              access through the Mobility Database API. MobilityData is not
              liable for any breaches of licensing terms by API users.
            </li>
          </ul>
        </Typography>
        <Typography sx={{ fontWeight: 700 }}>
          4. Modifications and Service Alterations
        </Typography>
        <Typography>
          <ul style={{ marginTop: 0 }}>
            <li>
              Modification Rights: MobilityData retains the right to modify the
              API service, including but not limited to feature modifications,
              suspensions, or discontinuations without prior notice.
              Furthermore, MobilityData has no obligation to provide access to
              the API and such access may be withdrawn at any time.
            </li>
            <li>
              Content Alterations: MobilityData reserves the right to modify the
              contents of the service at its discretion and without liability.
            </li>
          </ul>
        </Typography>
        <Typography sx={{ fontWeight: 700 }}>
          5. Service Availability
        </Typography>
        <Typography>
          Downgrades and Service Problems: Although MobilityData strives to
          provide exceptional service availability, MobilityData is not liable
          for any downgrades in service availability or disruptions in service
          performance.
        </Typography>
        <br />
        <Typography sx={{ fontWeight: 700 }}>6. Amendments to Terms</Typography>
        <Typography>
          MobilityData reserves the right to amend these Terms of Service at any
          time without prior notice. It is the responsibility of the API users
          to regularly review these terms for any changes.
        </Typography>
        <br />
        <Typography sx={{ fontWeight: 700 }}>7. Governing Law</Typography>
        <Typography>
          These Terms of Service shall be governed by and constructed in
          accordance with the laws of the province of Quebec and the federal
          laws of Canada applicable therein, without regard to any conflict of
          law principles which may require the application of the laws of
          another jurisdiction.
        </Typography>
        <br />
        <Typography sx={{ fontWeight: 700 }}>8. Contact Information</Typography>
        <Typography>
          For any queries or concerns regarding these Terms of Service, please
          contact MobilityData at
          <Button
            variant='text'
            href={'mailto:api@mobilitydata.org'}
            target={'_blank'}
            rel={'noreferrer'}
          >
            api@mobilitydata.org
          </Button>
        </Typography>
        <br />
        <Typography sx={{ fontWeight: 700 }}>
          Last Updated: January 23, 2024
        </Typography>
      </Box>
    </Container>
  );
}
