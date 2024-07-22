describe('Feed page', () => {
  beforeEach(() => {
    // (API mocking code remains the same)
    cy.visit('/feeds/mdb-516');
    cy.wait(100);
  });

  it('should render feed title and provider', () => {
    cy.get('[data-testid="feed-provider"]').should(
      'contain',
      'MTA New York City Transit (MTA)',
    );
    cy.get('[data-testid="feed-name"]').should('contain', 'NYC Subway');
  });

  it('should render the last updated date', () => {
    cy.get('[data-testid="last-updated"]').should('contain', 'Last updated on');
  });

  it('should render download button', () => {
    cy.get('[id="download-latest-button"]').should('exist');
  });

  it('should render data quality summary', () => {
    cy.get('[data-testid="data-quality-summary"]').within(() => {
      cy.get('[data-testid="error-count"]').should('contain', 'errors');
      cy.get('[data-testid="warning-count"]').should('contain', 'warnings');
      cy.get('[data-testid="info-count"]').should('contain', 'info notices');
    });
  });

  it('should render feed summary', () => {
    cy.get('[data-testid="location"]').should('exist');
    cy.get('[data-testid="producer-url"]').should('exist');
    cy.get('[data-testid="data-type"]').should('exist');
  });

  it('should render dataset history', () => {
    cy.get('[data-testid="dataset-item"]').should('have.length', 2);
  });

  it('should render feature chips', () => {
    cy.get('[data-testid="feature-chips"]').should('have.length', 5);
  });

  it('should have working links to validation reports', () => {
    cy.get('[data-testid="validation-report-html"]')
      .should('exist')
      .and('have.attr', 'href')
      .and('include', '.html');
    cy.get('[data-testid="validation-report-json"]')
      .should('exist')
      .and('have.attr', 'href')
      .and('include', '.json');
  });
});
