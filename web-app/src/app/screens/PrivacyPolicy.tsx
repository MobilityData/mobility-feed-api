import React from 'react';
import { Box, Container, Typography } from '@mui/material';
import CssBaseline from '@mui/material/CssBaseline';
export default function TermsAndConditions(): React.ReactElement {
  return (
    <Container component='main' sx={{ width: '100vw', m: 0 }}>
      <CssBaseline />
      <Box
        sx={{
          mt: 12,
          p: 10,
          pt: 2,
          display: 'flex',
          flexDirection: 'column',
          width: '100vw',
          background: '#F8F5F5',
        }}
      >
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 700, pb: 4 }}
        >
          Mobility Database Privacy Policy
        </Typography>
        <Typography sx={{ fontWeight: 700 }}>SEPTEMBER 2023 </Typography>
        <Typography>WRITTEN BY: Me Edward Smith, Legal Counsel</Typography>
        <Typography>
          WITH THE COLLABORATION OF: Me Daniel Cooper, Legal Advisor
        </Typography>
        <Typography>CORRECTED BY: Angelique Guillot </Typography>
        <Typography>
          ADAPTED FOR MOBILITYDATA AND TRANSLATED BY: Frédéric Simard
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Introduction
        </Typography>
        <Typography>
          The right to privacy is guaranteed by the Charter of Human Rights and
          Freedoms and the Civil Code of Québec. In addition, the protection of
          personal information is governed by the Act respecting the protection
          of personal information in the private sector.
        </Typography>
        <br />
        <Typography>
          {' '}
          This policy establishes a procedure for the management of personal
          information by the organization in order to collect, hold, conserve,
          use and communicate personal information on members, users,
          volunteers, staff and administrators of the organization in accordance
          with the law.{' '}
        </Typography>
        <br />
        <Typography>
          {' '}
          The person responsible for the protection of personal information
          (hereinafter referred to as the “responsible person”) within the
          organization is responsible for the application of and compliance with
          this policy by the organization’s representatives, whether they are
          current or former staff members, volunteers or directors.{' '}
        </Typography>
        <br />
        <Typography>
          {' '}
          In this respect, the person in charge publishes this policy on its
          website and makes it available to members, users, staff, volunteers or
          directors for consultation or training. In addition, the person in
          charge determines the directives and procedures necessary for the
          application of this policy.{' '}
        </Typography>

        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Objectives
        </Typography>
        <Typography>
          The purpose of this policy is to inform the organization’s members,
          users, staff, volunteers and administrators of the principles it
          applies in managing the personal information it holds on them. It also
          sets out the rules of conduct that the organization requires its
          members, users, staff, volunteers and directors to obey when they have
          access to personal information held on others by the organization. In
          applying this policy, the organization respects the following
          principles:{' '}
        </Typography>
        <Typography component='div'>
          <ul>
            <li>
              Collect only the personal information required for the proper
              management of operations;
            </li>
            <li>
              Notify individuals of the use and disclosure of their personal
              information as soon as it is required;
            </li>
            <li>
              Inform individuals of their rights, particularly with regard to
              complaints, and obtain their consent when required by law;
            </li>
            <li>
              Ensure the security and confidentiality of the personal
              information we hold on others, by overseeing its retention,
              rectification and destruction, and by defining the roles and
              responsibilities of our employees throughout its life cycle.
            </li>
            <li>
              In keeping with these principles, the organization occasionally
              purges and merges files, revises its forms and practices, updates
              and sets up a dedicated location for storing and consulting
              personal information.{' '}
            </li>
            <li>
              The organization may also undergo inspections by an independent
              assessor to validate the quality of its protection of personal
              information.
            </li>
          </ul>
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Definition of personal information
        </Typography>
        <Typography>
          Personal information is that which relates to a natural person and
          enables that person to be identified.
        </Typography>
        <Typography>
          This information is confidential and must be treated as such. Within
          the organization, personal information includes the following:
        </Typography>
        <Typography component='div'>
          <ul>
            <li>surname and given name;</li>
            <li>signature;</li>
            <li>residential address;</li>
            <li>medical records, prescription drugs;</li>
            <li>telephone number;</li>
            <li>e-mail address;</li>
            <li>image and voice of a person;</li>
            <li>biometric data;</li>
            <li>state of health;</li>
            <li>employment records;</li>
            <li>banking/financial information;</li>
            <li>Computer data</li>
            <li>
              Information concerning family, friends and other related persons
            </li>
            <li>Social insurance number</li>
            <li>Health insurance number and driver’s license number</li>
            <li>
              Any document on which this information is found or any document
              that refers to the existence of a particular person
            </li>
          </ul>
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Collection of personal information
        </Typography>
        <Typography>
          The organization collects personal information when it has a serious
          and legitimate interest in doing so. Personal information may be
          collected through forms on its website, by telephone interview,
          through a paper form, or through any interaction between individuals
          and the organization and/or its stakeholders.
        </Typography>
        <Typography>
          In particular, the organization collects personal information for the
          management of:
        </Typography>
        <Typography component='div'>
          <ul>
            <li>Member profiles</li>
            <li>User profiles</li>
            <li>Staff and volunteer profiles</li>
            <li>
              Incidents, including those with potential liability implications
              for the organization or anyone associated with it
            </li>
          </ul>
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Service inquiries.
        </Typography>
      </Box>
    </Container>
  );
}
