import { passwordValidatioError } from '../../src/app/types';

describe('Sign up screen', () => {
  beforeEach(() => {
    cy.visit('/sign-up');
  });

  it('should render components', () => {
    cy.get('input[id="email"]').should('exist');
    cy.get('input[id="password"]').should('exist');
    cy.get('input[id="confirmPassword"]').should('exist');
    cy.get('button[id="sign-up-button"]').should('exist');
  });

  it('should show the password error when password length is less than 12', () => {
    cy.get('input[id="password"]')
      .should('exist')
      .type('short', { force: true });

    cy.get('[data-testid=passwordError]')
      .should('exist')
      .contains(passwordValidatioError);
  });

  it('should show the password error when password do not contain lowercase', () => {
    cy.get('input[id="password"]')
      .should('exist')
      .type('UPPERCASE_10_!', { force: true });

    cy.get('[data-testid=passwordError]')
      .should('exist')
      .contains(passwordValidatioError);
  });

  it('should show the password error when password do not contain uppercase', () => {
    cy.get('input[id="password"]')
      .should('exist')
      .type('lowercase_10_!', { force: true });

    cy.get('[data-testid=passwordError]')
      .should('exist')
      .contains(passwordValidatioError);
  });

  it('should not show the password error when password is valid', () => {
    cy.get('input[id="password"]')
      .should('exist')
      .type('UP_lowercase_10_!', { force: true });

    cy.get('[data-testid=passwordError]').should('not.exist');
  });

  it('should show the password error when password do not match', () => {
    cy.get('input[id="password"]')
      .should('exist')
      .type('UP_lowercase_10_!', { force: true });

    cy.get('input[id="confirmPassword"]')
      .should('exist')
      .type('UP_lowercase_11_!', { force: true });

    cy.get('[data-testid=confirmPasswordError]')
      .should('exist')
      .contains('Passwords do not match');
  });
});
