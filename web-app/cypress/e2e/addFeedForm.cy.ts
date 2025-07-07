describe('Add Feed Form', () => {
  beforeEach(() => {
    cy.intercept('POST', '/writeToSheet', {
      statusCode: 200,
      body: {
        result: { message: 'Data written to the new sheet successfully!' },
      },
    });
    cy.visit('/');
    cy.get('[data-testid="home-title"]').should('exist');
    cy.createNewUserAndSignIn('cypressTestUser@mobilitydata.org', 'BigCoolPassword123!');

    cy.get('[data-cy="accountHeader"]').should('exist'); // assures that the user is signed in
    cy.visit('/contribute');
    // Assures that the firebase remote config has loaded for the first test
    // Optimizations can be made to make the first test run faster
    // Long timeout is to assure no flakiness
    cy.get('[data-cy=isOfficialProducerYes]', { timeout: 25000 }).should('exist');
  });

  describe('Success Flows', () => {
    it('should submit a new gtfs scheduled feed as official producer', () => {
      cy.get('[data-cy=isOfficialProducerYes]').click({ force: true });
      cy.muiDropdownSelect('[data-cy=isOfficialFeed]', 'yes');
      cy.get('[data-cy=feedLink] input').type('https://example.com/feed', { force: true });
      cy.get('[data-cy=submitFirstStep]').click();
      cy.url().should('include', '/contribute?step=2');
      // step 2
      cy.muiDropdownSelect('[data-cy=countryDropdown]', 'CA');
      cy.get('[data-cy=secondStepSubmit]').click();
      cy.url().should('include', '/contribute?step=3');
      // step 3: fill required emptyLicenseUsage if present
      cy.get('body').then($body => {
        if ($body.find('[data-cy="emptyLicenseUsage"]').length) {
          cy.get('[data-cy="emptyLicenseUsage"]').click();
          cy.contains('li', 'Unsure').click();
        }
      });
      cy.get('[data-cy=thirdStepSubmit]').click();
      cy.url().should('include', '/contribute?step=4');
      // step 4
      cy.get('[data-cy=dataProducerEmail] input').type('audio@stm.com', { force: true });
      cy.muiDropdownSelect('[data-cy=interestedInAudit]', 'no');
      cy.muiDropdownSelect('[data-cy=logoPermission]', 'yes');
      cy.get('[data-cy=fourthStepSubmit]').click();
      cy.url().should('include', 'contribute/submitted');
      //success check
      cy.get('[data-cy=feedSubmitSuccess]').should('exist');
    });

    it('should submit a new gtfs realtime feed as not official producer', () => {
      cy.get('[data-cy=isOfficialProducerNo]').click();
      cy.muiDropdownSelect('[data-cy=isOfficialFeed]', 'no');
      cy.muiDropdownSelect('[data-cy=dataType]', 'gtfs_rt');
      cy.get('[data-cy=submitFirstStep]').click();
      cy.url().should('include', '/contribute?step=2');
      // step 2
      cy.get('[data-cy=serviceAlertFeed] input').type(
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
      cy.assetMuiError('[data-cy=isOfficialFeedLabel]');
      cy.assetMuiError('[data-cy=isOfficialProducerLabel]');
      cy.assetMuiError('[data-cy=feedLinkLabel]');
      cy.assetMuiError('[data-cy=oldFeedLabel]');
      cy.location('pathname').should('eq', '/contribute');
      // Step 1 values
      cy.get('[data-cy=isOfficialProducerYes]').click();
      cy.muiDropdownSelect('[data-cy=isOfficialFeed]', 'yes');
      cy.get('[data-cy=feedLink] input').type('https://example.com/feed', { force: true });
      cy.get('[data-cy=oldFeedLink] input').type('https://example.com/feedOld');
      cy.get('[data-cy=submitFirstStep]').click();
      // Step 2
      cy.get('[data-cy=secondStepSubmit]').click();
      cy.assetMuiError('[data-cy=countryLabel]');
      cy.url().should('include', '/contribute?step=2');
      // Step 2 values
      cy.muiDropdownSelect('[data-cy=countryDropdown]', 'CA');
      cy.get('[data-cy=secondStepSubmit]').click();
      // Step 3: fill required emptyLicenseUsage if present
      cy.get('body').then($body => {
        if ($body.find('[data-cy="emptyLicenseUsage"]').length) {
          cy.get('[data-cy="emptyLicenseUsage"]').click();
          cy.contains('li', 'Unsure').click();
        }
      });
      cy.get('[data-cy=thirdStepSubmit]').click();
      // Step 4
      cy.get('[data-cy=fourthStepSubmit]').should('exist');
    });

    it('should display errors for gtfs-realtime feed', () => {
      cy.muiDropdownSelect('[data-cy=dataType]', 'gtfs_rt');
      cy.get('[data-cy=submitFirstStep]').click();
      cy.assetMuiError('[data-cy=isOfficialProducerLabel]');
      cy.assetMuiError('[data-cy=isOfficialFeedLabel]');
      cy.location('pathname').should('eq', '/contribute');
      // Step 1 values
      cy.get('[data-cy=isOfficialProducerYes]').click();
      cy.muiDropdownSelect('[data-cy=isOfficialFeed]', 'yes');
      cy.muiDropdownSelect('[data-cy=isUpdatingFeed]', 'yes');
      cy.get('[data-cy=submitFirstStep]').click();
      // Step 2
      cy.get('[data-cy=secondStepRtSubmit]').click();
      cy.assetMuiError('[data-cy=serviceAlertFeedLabel]');
      cy.assetMuiError('[data-cy=tripUpdatesFeedLabel]');
      cy.assetMuiError('[data-cy=vehiclePositionLabel]');
    });
  });

  it('should display and submit unofficialDesc and updateFreq fields when not official feed', () => {
    cy.get('[data-cy=isOfficialProducerNo]').click();
    cy.muiDropdownSelect('[data-cy=isOfficialFeed]', 'no');
    // Check that the new fields appear
    cy.get('[data-cy=unofficialDesc]').should('exist');
    cy.get('[data-cy=updateFreq]').should('exist');
    // Fill in the new fields (ensure only one element is targeted)
    cy.get('[data-cy=unofficialDesc] textarea').first().type('For research purposes', { force: true });
    cy.get('[data-cy=updateFreq] input').first().type('every month', { force: true });
    // Continue with the rest of the form
    cy.muiDropdownSelect('[data-cy=dataType]', 'gtfs');
    cy.get('[data-cy=feedLink] input').type('https://example.com/feed', { force: true });
    cy.get('[data-cy=submitFirstStep]').click();
    cy.url().should('include', '/contribute?step=2');
  });

  it('should show and require emptyLicenseUsage with Unsure option if official producer and no license', () => {
    cy.get('[data-cy=isOfficialProducerYes]').click();
    cy.muiDropdownSelect('[data-cy=isOfficialFeed]', 'yes');
    cy.get('[data-cy=feedLink] input').type('https://example.com/feed', { force: true });
    cy.get('[data-cy=submitFirstStep]').click();
    cy.url().should('include', '/contribute?step=2');
    // step 2: leave license blank
    cy.muiDropdownSelect('[data-cy=countryDropdown]', 'CA');
    cy.get('[data-cy=secondStepSubmit]').click();
    cy.url().should('include', '/contribute?step=3');
    // step 3: should see emptyLicenseUsage select
    cy.get('[data-cy="emptyLicenseUsage"]').should('exist');
    cy.get('[data-cy="emptyLicenseUsageLabel"]').should('contain', 'available for trip planners and other third parties to use');
    // Open dropdown and check options
    cy.get('[data-cy="emptyLicenseUsage"]').click();
    cy.get('li').should('contain', 'Yes');
    cy.get('li').should('contain', 'No');
    cy.get('li').should('contain', 'Unsure');
    cy.get('body').type('{esc}'); // close dropdown
    // Try submitting without selecting
    cy.get('[data-cy="thirdStepSubmit"]').click();
    cy.get('[data-cy="emptyLicenseUsageLabel"]').should('have.css', 'color').and('match', /rgb\(.*\)/);
    // Select Unsure and submit
    cy.get('[data-cy="emptyLicenseUsage"]').click();
    cy.contains('li', 'Unsure').click();
    cy.get('[data-cy="thirdStepSubmit"]').click();
    cy.url().should('include', '/contribute?step=4');
  });
});
