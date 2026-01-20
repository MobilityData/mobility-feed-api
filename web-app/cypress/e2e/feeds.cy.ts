/**
 * Feed page e2e tests
 *
 * API mocking is handled by MSW (Mock Service Worker) configured in:
 * - src/mocks/handlers.ts - API mock handlers
 * - src/mocks/server.ts - MSW server setup
 * - src/instrumentation.ts - Next.js instrumentation hook
 *
 * To enable mocking, start the Next.js server with:
 * NEXT_PUBLIC_API_MOCKING=enabled yarn start:dev
 *
 * Or use the .env.test file which has mocking enabled.
 */

// Test feed configuration - uses fixture data from cypress/fixtures/
const TEST_FEED_ID = 'test-516';
const TEST_FEED_DATA_TYPE = 'gtfs';

describe('Feed page', () => {
  beforeEach(() => {
    // Visit the feed detail page with the correct RSC route structure
    // Route: /feeds/[feedDataType]/[feedId]
    cy.visit(`feeds/${TEST_FEED_DATA_TYPE}/${TEST_FEED_ID}`, {
      timeout: 30000,
    });
  });

  it('should render feed title and provider', () => {
    cy.get('[data-testid="feed-provider"]', { timeout: 10000 }).should(
      'contain',
      'Metropolitan Transit Authority (MTA)',
    );
  });

  it('should render the last updated date', () => {
    cy.get('[data-testid="last-updated"]', { timeout: 10000 }).should('exist');
  });

  it('should render download button', () => {
    cy.get('[id="download-latest-button"]', { timeout: 10000 }).should('exist');
  });

  it('should render data quality summary', () => {
    cy.get('[data-testid="data-quality-summary"]', { timeout: 10000 }).within(
      () => {
        cy.get('[data-testid="error-count"]').should('exist');
        cy.get('[data-testid="warning-count"]').should('exist');
        cy.get('[data-testid="info-count"]').should('exist');
      },
    );
  });

  it('should render feed summary', () => {
    cy.get('[data-testid="location"]', { timeout: 10000 }).should('exist');
    cy.get('[data-testid="producer-url"]').should('exist');
    cy.get('[data-testid="data-type"]').should('exist');
  });

  it('should render dataset history', () => {
    // Fixture has 2 datasets
    cy.get('[data-testid="dataset-item"]', { timeout: 10000 }).should(
      'have.length',
      2,
    );
  });

  it('should render feature chips when available', () => {
    // Feature chips from fixture validation report
    cy.get('[data-testid="feature-chips"]', { timeout: 10000 }).should(
      'have.length.at.least',
      1,
    );
  });

  it('should have working links to validation reports', () => {
    cy.get('[data-testid="validation-report-html"]', { timeout: 10000 })
      .should('exist')
      .and('have.attr', 'href')
      .and('include', '.html');
    cy.get('[data-testid="validation-report-json"]')
      .should('exist')
      .and('have.attr', 'href')
      .and('include', '.json');
  });
});
