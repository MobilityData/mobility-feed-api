
describe('Reset Password Screen', () => {
  beforeEach(() => {
    cy.visit('/forgot-password');
  });

  it('should render components', () => {
    cy.get('input[id="email"]').should('exist');
  });

  it('should show error when email no email is provided', () => {
    cy.get('input[id="email"]').type('not an email', { force: true });

    cy.get('[data-testid=emailError]')
      .should('exist')
  });

  it('should show error when email is invalid', () => {
    cy.get('input[id="email"]').type('notvalid@e.c', { force: true });
    cy.get('[type="submit"]').click();
    cy.get('[data-testid=firebaseError]')
      .should('exist')
  });

  it('should show error when user doesn\'t exist', () => {
    cy.get('input[id="email"]').type('userdontexist@email.ca', { force: true });
    cy.get('[type="submit"]').click();
    cy.get('[data-testid=firebaseError]')
      .should('exist')
  });
});
