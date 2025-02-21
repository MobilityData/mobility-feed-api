import React from 'react';
import { Box, Container, Typography, useTheme } from '@mui/material';
import CssBaseline from '@mui/material/CssBaseline';
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
          Privacy Policy
        </Typography>
        <Typography sx={{ fontWeight: 700 }}>SEPTEMBER 2023 </Typography>
        <br />
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
        <Typography paragraph>
          The right to privacy is guaranteed by the Charter of Human Rights and
          Freedoms and the Civil Code of Québec. In addition, the protection of
          personal information is governed by the Act respecting the protection
          of personal information in the private sector.
        </Typography>
        <Typography paragraph>
          This policy establishes a procedure for the management of personal
          information by the organization in order to collect, hold, conserve,
          use and communicate personal information on members, users,
          volunteers, staff and administrators of the organization in accordance
          with the law.
        </Typography>
        <Typography paragraph>
          The person responsible for the protection of personal information
          (hereinafter referred to as the “responsible person”) within the
          organization is responsible for the application of and compliance with
          this policy by the organization’s representatives, whether they are
          current or former staff members, volunteers or directors.{' '}
        </Typography>
        <Typography paragraph>
          In this respect, the person in charge publishes this policy on its
          website and makes it available to members, users, staff, volunteers or
          directors for consultation or training. In addition, the person in
          charge determines the directives and procedures necessary for the
          application of this policy.
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Objectives
        </Typography>
        <Typography paragraph>
          The purpose of this policy is to inform the organization’s members,
          users, staff, volunteers and administrators of the principles it
          applies in managing the personal information it holds on them. It also
          sets out the rules of conduct that the organization requires its
          members, users, staff, volunteers and directors to obey when they have
          access to personal information held on others by the organization.
        </Typography>
        <Typography>
          In applying this policy, the organization respects the following
          principles:
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
        <Typography paragraph>
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
            <li>Computer data;</li>
            <li>
              Information concerning family, friends and other related persons;
            </li>
            <li>Social insurance number;</li>
            <li>Health insurance number and driver’s license number;</li>
            <li>
              Any document on which this information is found or any document
              that refers to the existence of a particular person.
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
        <Typography paragraph>
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
            <li>Member profiles;</li>
            <li>User profiles;</li>
            <li>Staff and volunteer profiles;</li>
            <li>
              Incidents, including those with potential liability implications
              for the organization or anyone associated with it;
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
        <Typography paragraph>
          When collecting personal information, the organization retains only
          that which is necessary for its proper functioning. The organization
          is able to justify why it requires each piece of personal information.
        </Typography>

        <Typography paragraph>
          The organization may, however, collect such personal information from
          a third party without the consent of the person concerned, if the
          collection, although made in his or her interest, cannot be made from
          him or her in a timely manner. It may also do so to verify the
          accuracy of the information obtained from the person concerned, or if
          authorized by law.
        </Typography>

        <Typography paragraph>
          Information that is already or becomes known to the public
          (information on websites or social media profiles) may also be
          collected by the organization without having to transmit it directly.
          In such cases, the organization nevertheless undertakes to collect the
          information in a reasonable and discerning manner.
        </Typography>

        <Typography paragraph>
          When the organization collects personal information from a legal
          entity, it records the source of this information, unless it is part
          of an investigation to prevent, detect or punish a crime or a breach
          of the law.
        </Typography>

        <Typography paragraph>
          Before the organization collects any personal information, it informs
          the person concerned:
        </Typography>
        <Typography component='div'>
          <ul>
            <li>
              The purposes for which the information is collected (collection);
            </li>
            <li>The means by which the information is collected;</li>
            <li>
              Of his or her right to withdraw consent to the disclosure or use
              of the information collected;
            </li>
            <li>
              The name of the third party for whom the information is being
              collected;
            </li>
            <li>
              Contact information for the person responsible for protecting
              personal information;
            </li>
            <li>
              The categories of persons, including third parties, who may have
              access to it;
            </li>
            <li>Where your personal information will be stored;</li>
            <li>The safeguards in place;</li>
            <li>Access and rectification rights provided by law.</li>
          </ul>
        </Typography>
        <Typography paragraph>
          If the person concerned refuses to provide the personal information
          requested by the organization or refuses to consent to the exchange of
          personal information with a third party, it is up to the person
          responsible to decide whether or not to deal with the person
          concerned.
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Protection of personal information
        </Typography>
        <Typography>
          Physical files containing confidential information are kept under lock
          and key in a filing cabinet or in a location dedicated to this purpose
          by the person in charge and to which access is secured. Employees are
          prohibited from leaving the workplace with personal information
          without the organization’s approval.
        </Typography>
        <Typography paragraph>
          Personal information is stored on a cloud server for which a secure
          password is required. The organization has a firewall and anti-virus
          software to limit the scope of malicious attacks.
        </Typography>
        <Typography>
          The following categories of persons have access to personal
          information when required for the performance of their duties:
        </Typography>
        <Typography component='div'>
          <ul>
            <li>Members of the Board of Directors and General Management;</li>
            <li>Employees.</li>
          </ul>
        </Typography>
        <Typography paragraph>
          The employment contracts of all employees, which all must sign,
          contain four clauses in the Confidentiality section, at points 7.1,
          7.2, 7.3 and 7.4, which constitute a commitment to confidentiality
          under the terms of Quebec’s Bill 25. The organization also ensures
          that it sets out the roles and responsibilities of its staff
          throughout the life cycle of this information, so that they understand
          how to implement the policy in their day-to-day work.
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Policy Manager
        </Typography>
        <Typography paragraph>
          Frédéric Simard is responsible for the protection of personal
          information within the organization, in compliance with section 3.1 of
          the Act respecting the protection of personal information in the
          private sector. Mr. Simard is responsible for the organization’s
          information technologies and cybersecurity. He can be reached at
          frederic-contractor@mobilitydata.org.
        </Typography>
        <Typography paragraph>
          In addition to his other duties, the person in charge also ensures
          that the organization’s staff understands the issues involved in
          protecting personal information.
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Use of personal information
        </Typography>
        <Typography paragraph>
          Personal information collected by the organization is used or
          disclosed only for the purposes for which it was collected, unless the
          individual concerned consents or it is required by law. Personal
          information is primarily used to facilitate the provision of services
          to members, customers and users. However, it may also be used for
          purposes of market research, newsletter distribution (it will be
          possible to unsubscribe at any time), personnel hiring or for any
          other reason detailed at the time of collection of personal
          information.
        </Typography>
        <Typography paragraph>
          Personal information will never be sold to third parties, unless the
          organization obtains consent to do so. The organization also ensures
          that the personal information it holds on others is up-to-date and
          accurate at the time it is used to make a decision about the
          individual concerned.
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Retention and destruction of personal information
        </Typography>
        <Typography paragraph>
          Once the purpose for which personal information was collected has been
          fulfilled, the organization destroys it, unless there are exceptional
          circumstances. In accordance with the law, personal information is
          retained for as long as applicable laws require. Personal information
          that is the subject of a request for access or rectification is
          retained until all legal remedies have been exhausted. In addition,
          the organization retains personal information for the length of time
          required by the government authorities to which it is accountable.
        </Typography>
        <Typography paragraph>
          Subject to other legal/ethical obligations regarding the retention of
          files by the organization and those working on its behalf, the person
          concerned may request that any file concerning him or her be returned
          to him or her, and that any personal information otherwise held by the
          organization be destroyed. The destruction of personal information may
          also make it impossible for the organization to continue offering
          goods or services. The same applies in the event that the person
          concerned no longer consents to this policy.
        </Typography>
        <Typography paragraph>
          The organization does not discard any document that contains personal
          information that can be reconstructed. Whenever possible, such
          documents are destroyed or shredded. Failing this, the organization
          will, as appropriate, format, rewrite, digitally shred, degauss or
          overwrite the information.
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Right of access and transfer of personal information
        </Typography>
        <Typography paragraph>
          At the verbal or written request of a person concerned or of a person
          establishing his or her capacity as representative, heir, successor,
          administrator of the estate, beneficiary of life insurance or holder
          of parental authority over the person concerned, the organization
          confirms that it holds personal information relating to the person
          concerned.
        </Typography>
        <Typography paragraph>
          At the written request of a person concerned or of one of the persons
          designated in the preceding paragraph, the organization allows him or
          her, within thirty (30) days of receipt of the request, to consult or
          transfer, as the case may be, its file or that of the person
          concerned, and discloses to him or her any personal information
          contained therein. However, the organization may refuse to disclose
          personal information in the following cases:
        </Typography>
        <Typography paragraph>
          It does not concern the interests and rights of the person requesting
          it as liquidator, beneficiary, heir or successor to the liquidator of
          the succession;
        </Typography>
        <Typography>
          It would likely reveal personal information about a third party, or
          the existence of such information, and such disclosure would be likely
          to cause serious harm to the third party, unless the third party
          consents;
        </Typography>
        <Typography paragraph>
          It is prohibited by law, an ongoing investigation or a court order.
        </Typography>
        <Typography paragraph>
          In the event of refusal, the organization will give reasons in writing
          to the person concerned within the same period of thirty (30) days and
          inform him or her of his or her right to contest the decision before
          the Commission d’accès à l’information or CAI (Quebec’s Commission for
          access to information). If the organization fails to respond to a
          request for access within this period, it is deemed to have refused
          access, in which case the interested party may apply to the Commission
          d’accès à l’information (CAI) to assert his or her rights.
        </Typography>
        <Typography paragraph>
          Notwithstanding the foregoing, the organization may not refuse to
          disclose personal information concerning an individual in the event of
          an emergency that threatens the life, health or security of the
          individual.
        </Typography>
        <Typography paragraph>
          However, the organization may temporarily refuse to consult the
          personal health information it holds on the person concerned if this
          would cause serious harm to his or her health, on condition that it
          offers to designate a health professional to receive the communication
          of such information and to communicate it to the latter. This
          professional then determines when the consultation can take place and
          notifies the person concerned.
        </Typography>
        <Typography paragraph>
          Finally, unless the request is made by the holder of parental
          authority, the organization refuses to communicate to a person under
          the age of 14 any medical or social information concerning him or her,
          or refuses to inform him or her of the existence of such information
          in a file kept on him or her, except through his or her lawyer in the
          context of legal proceedings. This does not restrict normal
          communications between a health and social services professional and
          his or her patient.
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Request for rectification of personal information
        </Typography>
        <Typography paragraph>
          At the written request of the person concerned or of a person
          designated in the first paragraph of the “Right of access and transfer
          of personal information” section, the organization will, within thirty
          (30) days of receipt of the request, rectify inaccurate, incomplete or
          equivocal information, as the case may be, in its file or in the file
          of the person concerned, add comments or delete information that is
          outdated, not justified by the purpose of the file or the collection
          of which was not authorized by law.
        </Typography>
        <Typography paragraph>
          In the event of refusal, the organization must give reasons in writing
          to the person concerned within the same thirty (30) day period, and
          inform him or her of his or her right to contest the decision before
          the Commission d’accès à l’information (CAI) If the organization fails
          to respond to a request for rectification within this time limit, it
          is deemed to have refused to acquiesce, in which case the person
          concerned may apply to the Commission d’accès à l’information (CAI) to
          assert his or her rights.
        </Typography>
        <Typography paragraph>
          By agreeing to a request for rectification, the organization provides
          the applicant, free of charge, with a copy of any personal information
          that has been modified or added, or, as the case may be, an
          attestation of the removal of personal information.{' '}
        </Typography>
        <Typography paragraph>
          It is the responsibility of individuals who have provided personal
          information to notify the organization of any changes to that
          information. The organization cannot be held responsible for any
          failure to carry out a rectification request when it should have been
          made.
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Charges for transcription, reproduction or transmission of personal
          information
        </Typography>
        <Typography>
          The organization charges reasonable fees for the transcription,
          reproduction or transmission of personal information. These fees are
          established by the person responsible and are subject to periodic
          review.
        </Typography>
        <Typography paragraph>
          Before proceeding with the transcription, reproduction or transmission
          of such information, the organization will inform the applicant of the
          approximate amount payable.
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Transmission of documents containing personal information
        </Typography>
        <Typography paragraph>
          When transmitting documents electronically, the organization’s
          representatives must indicate the confidential nature of the
          transmission in the subject line and, in the message, the
          confidentiality notice inviting the recipient to contact the sender
          without delay in the event of receipt in error. As a minimum, the
          organization’s representatives must indicate their email address, name
          and contact telephone number in their exchanges.
        </Typography>
        <Typography paragraph>
          When sending documents by post, the organization’s representatives
          must clearly indicate on the packaging the name and address of the
          person authorized to receive the documents. They enclose a letter
          specifying the confidential nature of the information and a
          confidentiality notice inviting the recipient to contact the sender
          without delay in the event of mistaken receipt.
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Definition of a confidentiality incident
        </Typography>
        <Typography paragraph>
          In accordance with the Act respecting the protection of personal
          information in the private sector, a confidentiality incident can take
          the following forms:
        </Typography>
        <Typography component='div'>
          <ul>
            <li>Access to personal information not authorized by law;</li>
            <li>Unauthorized use or disclosure of personal information;</li>
            <li>
              The loss of personal information or any other breach in the
              protection of such information.
            </li>
          </ul>
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Process in the event of a privacy incident
        </Typography>
        <Typography paragraph>
          In the event of an incident involving personal information, the
          organization follows the procedure set out in the Act respecting the
          protection of personal information in the private sector and its
          related regulations. When an incident presents a risk of serious
          prejudice, the Commission d’accès à l’information (CAI) and the
          persons concerned by the incident will be notified as quickly as
          possible following knowledge of the incident, insofar as the situation
          permits. The content of these notices is set out in Appendices 1 and 2
          respectively.
        </Typography>

        <Typography paragraph>
          If third parties need to be contacted in order to mitigate the damage
          that may result from the incident, the person responsible for the
          protection of personal information will ensure that only the personal
          information required for this purpose is communicated, and that this
          communication is recorded. An incident log will be maintained by the
          Privacy Officer. The contents of this register can be found in
          Appendix 3.
        </Typography>

        <Typography paragraph>
          By transmitting personal information to the organization, it is
          understood that the persons concerned understand that the organization
          deploys best work practices and protection mechanisms in order to
          limit the possibility of any incident, leak or misuse of personal
          information. However, the organization cannot guarantee infallible
          security for every conceivable scenario.
        </Typography>

        <Typography paragraph>
          If a data subject notices that an incident involving his or her
          personal information may have occurred within the organization, he or
          she should contact the person responsible for the protection of
          personal information at the coordinates shown above.
          Complaints/reports are processed within a maximum of thirty (30) days
          after they are filed.
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Inapplicability of the policy
        </Typography>
        <Typography paragraph>
          When a data subject leaves the organization’s website for any other
          website linked to the organization’s website, this policy no longer
          applies. Please refer to their policy, if applicable.
        </Typography>
        <Typography paragraph>
          When a law, regulation or court order compels the organization to
          transmit personal information, it is understood that the organization
          cannot guarantee the level of confidentiality and security instituted
          by the person or government that has been granted it.
        </Typography>
        <Typography paragraph>
          In the event of a merger or other legal reorganization of the
          organization, all personal information may be transferred to the new
          legal entity.
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Policy modification
        </Typography>
        <Typography>
          Any modification will be updated on the organization’s website and
          sent to the e-mail address of the persons concerned if they have been
          forwarded.
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Adoption and coming into force of this policy
        </Typography>
        <Typography>This policy was adopted on: September 22, 2023</Typography>
        <Typography>This policy takes effect on: September 22, 2023</Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 700, pb: 4 }}
        >
          APPENDICES
        </Typography>
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Appendix 1 – Contents of the notice to the CAI in the event of a
          confidentiality incident
        </Typography>
        <Typography>The CAI notice contains:</Typography>
        <Typography component='div'>
          <ul>
            <li>Name and NEQ of the organization</li>
            <li>
              The name of the person responsible for the protection of personal
              information
            </li>
            <li>
              A description of the personal information affected by the incident
              (if this information is not known, the reason for not being able
              to provide such a description)
            </li>
            <li>
              A brief description of the circumstances of the incident (and, if
              known, its Cause)
            </li>
            <li>
              The date or period when the incident took place (and, if unknown,
              an approximation)
            </li>
            <li>
              The date or period during which the organization became aware of
              the incident
            </li>
            <li>
              The number of people affected by the incident and, among them, the
              number of Quebec residents (or, if unknown, an approximation of
              these numbers)
            </li>
            <li>
              A description of the factors that lead the organization to
              conclude that there is a risk of serious harm being caused to the
              people concerned
            </li>
            <li>
              The measures that the organization has taken or intends to take to
              notify the persons concerned (including the date on which the
              persons were notified or the timeframe envisaged for completion)
            </li>
            <li>
              The measures the organization has taken or intends to take
              following the occurrence of the incident (including the date or
              period when the measures were taken, or the timeframe envisaged
              for their completion)
            </li>
            <li>
              Where applicable, a statement to the effect that a person or
              organization outside Quebec with similar responsibilities to CAI
              has been notified of the incident.
            </li>
          </ul>
        </Typography>
        <Typography>
          The information provided in the notice must be updated in the event of
          subsequent changes.
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Appendix 2 – Contents of the notice to data subjects in the event of a
          confidentiality incident
        </Typography>
        <Typography>The notice to data subjects contains:</Typography>
        <Typography component='div'>
          <ul>
            <li>
              A description of the personal information affected by the incident
              (if this information is not known, the reason for not being able
              to provide such a description).
            </li>
            <li>A brief description of the circumstances of the incident.</li>
            <li>
              The date or period when the incident took place (and, if unknown,
              an approximation).
            </li>
            <li>
              A brief description of the measures that the organization has
              taken or intends to take following the incident, in order to
              reduce the risk of harm being caused.
            </li>
            <li>
              Measures the organization suggests the person concerned take to
              reduce the risk of harm being caused, or to mitigate such harm.
            </li>
            <li>
              Contact details enabling the person concerned to obtain further
              information about the incident.
            </li>
          </ul>
        </Typography>
        <Typography>The notice may be public if:</Typography>
        <Typography component='div'>
          <ul>
            <li>
              Passing on the notice is likely to cause greater harm to the
              person concerned
            </li>
            <li>
              Providing the notice is likely to cause undue hardship to the
              organization
            </li>
            <li>
              The organization does not have the contact details of the person
              concerned
            </li>
            <li>
              The organization does not find itself in one of the three cases
              listed above, but wishes to inform the persons concerned quickly,
              without neglecting to send them a notice directly afterwards
            </li>
          </ul>
        </Typography>
        <br />
        <Typography
          variant='h4'
          color='primary'
          sx={{ fontWeight: 500, pb: 4 }}
        >
          Appendix 3 – Contents of the confidentiality incident register
        </Typography>
        <Typography component='div'>
          <ul>
            <li>Incident number (for internal reference).</li>
            <li>
              A description of the personal information affected by the incident
              (if this information is not known, the reason for not being able
              to provide such a description).
            </li>
            <li>A brief description of the circumstances of the incident.</li>
            <li>
              The date or period when the incident took place (and, if unknown,
              an approximation).
            </li>
            <li>
              The date or period during which the organization became aware of
              the incident.
            </li>
            <li>
              The number of persons concerned by the incident (or, if not known,
              an approximation of this number).
            </li>
            <li>
              A description of the factors that lead the organization to
              conclude that there is a risk of serious harm being caused to the
              people concerned.
            </li>
            <li>
              The dates on which notifications were sent to CAI and to the
              persons concerned, as well as an indication of whether public
              notifications were given by the organization and why, if so.
            </li>
            <li>
              A brief description of the measures taken by the organization,
              following the occurrence of the incident, to reduce the risk of
              harm being caused.
            </li>
          </ul>
        </Typography>
        <Typography>
          The information contained in the register must be kept up to date and
          retained for a minimum period of five years after the date or period
          during which the organization became aware of the incident.
        </Typography>
      </Box>
    </Container>
  );
}
