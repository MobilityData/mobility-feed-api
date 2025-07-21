import feedJson from '../fixtures/feed_test-516.json';
import gtfsFeedJson from '../fixtures/gtfs_feed_test-516.json';
import datasetsFeedJson from '../fixtures/feed_datasets_test-516.json';

const apiBaseUrl = '**';

describe('Feed page', () => {
  beforeEach(() => {
    cy.intercept('GET', `${apiBaseUrl}/v1/feeds/test-516`, feedJson);
    cy.intercept('GET', `${apiBaseUrl}/v1/gtfs_feeds/test-516`, gtfsFeedJson);
    cy.intercept(
      'GET',
      `${apiBaseUrl}/v1/gtfs_feeds/test-516/datasets?offset=0&limit=10`,
      datasetsFeedJson,
    );
    cy.visit('feeds/test-516');
  });

  it('should render feed title and provider', () => {
    cy.get('[data-testid="feed-provider"]').should(
      'contain',
      'Metropolitan Transit Authority (MTA)',
    );
    cy.get('[data-testid="feed-name"]').should('contain', 'NYC Subway');
  });

  it('should render the last updated date', () => {
    cy.get('[data-testid="last-updated"]').should(
      'contain',
      'Quality report updated',
    );
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
