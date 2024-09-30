describe('Add Feed Form', () => {
  beforeEach(() => {
    cy.viewport(1280, 720);
    cy.visit('/');
    cy.get('[data-testid="home-title"]').should('exist');
    cy.visit('/contribute');
    cy.injectAuthenticatedUser();
    cy.intercept('POST', '/writeToSheet', {
      statusCode: 200,
      body: {
        result: { message: 'Data written to the new sheet successfully!' },
      },
    }).as('writeToSheet');
  });

  describe('Success Flows', () => {
    it('should submit a new gtfs scheduled feed as official producer', () => {
      cy.get('[data-cy=isOfficialProducerYes]', { timeout: 6000 }).click({
        force: true,
      });
      cy.get('[data-cy=feedLink] input').type('https://example.com/feed', {
        force: true,
      });
      cy.get('[data-cy=submitFirstStep]').click({ force: true });
      cy.url().should('include', '/contribute?step=2');
      // step 2
      cy.muiDropdownSelect('[data-cy=countryDropdown]', 'CA');
      cy.get('[data-cy=secondStepSubmit]').click({ force: true });
      cy.url().should('include', '/contribute?step=3');
      // step 3
      cy.get('[data-cy=thirdStepSubmit]').click({ force: true });
      cy.url().should('include', '/contribute?step=4');
      // step 4
      cy.get('[data-cy=dataProducerEmail] input').type('audio@stm.com', {
        force: true,
      });
      cy.muiDropdownSelect('[data-cy=interestedInAudit]', 'no');
      cy.muiDropdownSelect('[data-cy=logoPermission]', 'yes');
      cy.get('[data-cy=fourthStepSubmit]').click({ force: true });
      cy.url().should('include', 'contribute/submitted');
      //success check
      cy.get('[data-cy=feedSubmitSuccess]').should('exist');
    });

    it('should submit a new gtfs realtime feed as not official producer', () => {
      cy.get('[data-cy=isOfficialProducerNo]').click({ force: true });
      cy.muiDropdownSelect('[data-cy=dataType]', 'gtfs_rt');
      cy.get('[data-cy=submitFirstStep]').click({ force: true });
      cy.url().should('include', '/contribute?step=2');
      // step 2
      cy.get('[data-cy=serviceAlertFeed] input').type(
        'https://example.com/feed/realtime',
        { force: true },
      );
      cy.get('[data-cy=secondStepRtSubmit]').click({ force: true });
      cy.url().should('include', '/contribute?step=3');
      // step 3
      cy.get('[data-cy=thirdStepSubmit]').click({ force: true });
      cy.url().should('include', 'contribute/submitted');
      // success check
      cy.get('[data-cy=feedSubmitSuccess]').should('exist');
    });
  });

  describe('Error Flows', () => {
    it('should display errors for gtfs feed', () => {
      cy.muiDropdownSelect('[data-cy=isUpdatingFeed]', 'yes');
      cy.get('[data-cy=submitFirstStep]').click({ force: true });
      cy.assetMuiError('[data-cy=isOfficialProducerLabel]');
      cy.assetMuiError('[data-cy=feedLinkLabel]');
      cy.assetMuiError('[data-cy=oldFeedLabel]');
      cy.location('pathname').should('eq', '/contribute');
      // Step 1 values
      cy.get('[data-cy=isOfficialProducerYes]').click({ force: true });
      cy.get('[data-cy=feedLink] input').type('https://example.com/feed', {
        force: true,
      });
      cy.get('[data-cy=oldFeedLink] input').type(
        'https://example.com/feedOld',
        { force: true },
      );
      cy.get('[data-cy=submitFirstStep]').click({ force: true });
      // Step 2
      cy.get('[data-cy=secondStepSubmit]').click({ force: true });
      cy.assetMuiError('[data-cy=countryLabel]');
      cy.url().should('include', '/contribute?step=2');
      // Step 2 values
      cy.muiDropdownSelect('[data-cy=countryDropdown]', 'CA');
      cy.get('[data-cy=secondStepSubmit]').click({ force: true });
      // Step 3
      cy.muiDropdownSelect('[data-cy=isAuthRequired]', 'choiceRequired');
      cy.get('[data-cy=thirdStepSubmit]').click({ force: true });
      cy.assetMuiError('[data-cy=authTypeLabel]');
      cy.assetMuiError('[data-cy=authSignupLabel]');
      // Step 3 values
      cy.muiDropdownSelect('[data-cy=isAuthRequired]', 'None - 0');
      cy.get('[data-cy=thirdStepSubmit]').click({ force: true });
      // Step 4
      cy.get('[data-cy=fourthStepSubmit]').click({ force: true });
      cy.assetMuiError('[data-cy=dataProducerEmailLabel]');
      cy.assetMuiError('[data-cy=dataAuditLabel]');
      cy.assetMuiError('[data-cy=logoPermissionLabel]');
    });

    it('should display errors for gtfs-realtime feed', () => {
      cy.muiDropdownSelect('[data-cy=dataType]', 'gtfs_rt');
      cy.get('[data-cy=submitFirstStep]').click({ force: true });
      cy.assetMuiError('[data-cy=isOfficialProducerLabel]');
      cy.location('pathname').should('eq', '/contribute');
      // Step 1 values
      cy.get('[data-cy=isOfficialProducerYes]').click({ force: true });
      cy.muiDropdownSelect('[data-cy=isUpdatingFeed]', 'yes');
      cy.get('[data-cy=submitFirstStep]').click({ force: true });
      // Step 2
      cy.get('[data-cy=secondStepRtSubmit]').click({ force: true });
      cy.assetMuiError('[data-cy=serviceAlertFeedLabel]');
      cy.assetMuiError('[data-cy=tripUpdatesFeedLabel]');
      cy.assetMuiError('[data-cy=vehiclePositionLabel]');
    });
  });
});
