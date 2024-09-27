describe('Add Feed Form', () => {
  beforeEach(() => {
    cy.visit('/');
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
      cy.get('[data-cy=isOfficialProducerYes]').click();
      cy.get('[data-cy=feedLink]').type('https://example.com/feed');
      cy.get('[data-cy=submitFirstStep]').click();
      cy.url().should('include', '/contribute?step=2');
      // step 2
      cy.muiDropdownSelect('[data-cy=countryDropdown]', 'CA');
      cy.get('[data-cy=secondStepSubmit]').click();
      cy.url().should('include', '/contribute?step=3');
      // step 3
      cy.get('[data-cy=thirdStepSubmit]').click();
      cy.url().should('include', '/contribute?step=4');
      // step 4
      cy.get('[data-cy=dataProducerEmail]').type('audio@stm.com');
      cy.muiDropdownSelect('[data-cy=interestedInAudit]', 'no');
      cy.muiDropdownSelect('[data-cy=logoPermission]', 'yes');
      cy.get('[data-cy=fourthStepSubmit]').click();
      cy.url().should('include', 'contribute/submitted');
      //success check
      cy.get('[data-cy=feedSubmitSuccess]').should('exist');
    });

    it('should submit a new gtfs realtime feed as not official producer', () => {
      cy.get('[data-cy=isOfficialProducerNo]').click();
      cy.muiDropdownSelect('[data-cy=dataType]', 'gtfs_rt');
      cy.get('[data-cy=submitFirstStep]').click();
      cy.url().should('include', '/contribute?step=2');
      // step 2
      cy.get('[data-cy=serviceAlertFeed]').type(
        'https://example.com/feed/realtime',
      );
      cy.get('[data-cy=secondStepRtSubmit]').click();
      cy.url().should('include', '/contribute?step=3');
      // step 3
      cy.get('[data-cy=thirdStepSubmit]').click();
      cy.url().should('include', 'contribute/submitted');
      // success check
      cy.get('[data-cy=feedSubmitSuccess]').should('exist');
    });
  });

  describe('Error Flows', () => {
    it('should display errors for gtfs feed', () => {
      cy.muiDropdownSelect('[data-cy=isUpdatingFeed]', 'yes');
      cy.get('[data-cy=submitFirstStep]').click();
      cy.assetMuiError('[data-cy=isOfficialProducerLabel]');
      cy.assetMuiError('[data-cy=feedLinkLabel]');
      cy.assetMuiError('[data-cy=oldFeedLabel]');
      cy.location('pathname').should('eq', '/contribute');
      // Step 1 values
      cy.get('[data-cy=isOfficialProducerYes]').click();
      cy.get('[data-cy=feedLink]').type('https://example.com/feed');
      cy.get('[data-cy=oldFeedLink]').type('https://example.com/feedOld');
      cy.get('[data-cy=submitFirstStep]').click();
      // Step 2
      cy.get('[data-cy=secondStepSubmit]').click();
      cy.assetMuiError('[data-cy=countryLabel]');
      cy.url().should('include', '/contribute?step=2');
      // Step 2 values
      cy.muiDropdownSelect('[data-cy=countryDropdown]', 'CA');
      cy.get('[data-cy=secondStepSubmit]').click();
      // Step 3
      cy.muiDropdownSelect('[data-cy=isAuthRequired]', 'choiceRequired');
      cy.get('[data-cy=thirdStepSubmit]').click();
      cy.assetMuiError('[data-cy=authTypeLabel]');
      cy.assetMuiError('[data-cy=authSignupLabel]');
      // Step 3 values
      cy.muiDropdownSelect('[data-cy=isAuthRequired]', 'None - 0');
      cy.get('[data-cy=thirdStepSubmit]').click();
      // Step 4
      cy.get('[data-cy=fourthStepSubmit]').click();
      cy.assetMuiError('[data-cy=dataProducerEmailLabel]');
      cy.assetMuiError('[data-cy=dataAuditLabel]');
      cy.assetMuiError('[data-cy=logoPermissionLabel]');
    });

    it('should display errors for gtfs-realtime feed', () => {
      cy.get('[data-cy=dataType]')
        .click()
        .get('ul > li[data-value="gtfs_rt"]')
        .click();
      cy.get('[data-cy=submitFirstStep]').click();
      cy.assetMuiError('[data-cy=isOfficialProducerLabel]');
      cy.location('pathname').should('eq', '/contribute');
      // Step 1 values
      cy.get('[data-cy=isOfficialProducerYes]').click();
      cy.muiDropdownSelect('[data-cy=isUpdatingFeed]', 'yes');
      cy.get('[data-cy=submitFirstStep]').click();
      // Step 2
      cy.get('[data-cy=secondStepRtSubmit]').click();
      cy.assetMuiError('[data-cy=serviceAlertFeedLabel]');
      cy.assetMuiError('[data-cy=tripUpdatesFeedLabel]');
      cy.assetMuiError('[data-cy=vehiclePositionLabel]');
    });
  });
});
