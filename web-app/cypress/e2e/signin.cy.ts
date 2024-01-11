describe('Sign In page', () => {
  beforeEach(() => {
    cy.visit('/sign-in');
  });

  it('should render page header', () => {
    cy.get('[data-testid=websiteTile]')
      .should('exist')
      .contains('Mobility Database');
  });

  it('should render signin', () => {
    cy.get('[data-testid=signin]').should('exist');
  });
});
