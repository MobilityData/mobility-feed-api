describe('Sign up screen', () => {
  beforeEach(() => {
    cy.visit('/sign-up');
  });

  it('should render components', () => {
    cy.get('input[id="email"]').should('exist');
    cy.get('input[id="password"]').should('exist');
    cy.get('input[id="confirmPassword"]').should('exist');
    cy.get('button[id="sign-up-button"]').should('exist');
    cy.get('input[id="agreeToTerms"]').should('exist');
    cy.get('iframe[title="reCAPTCHA"]').should('exist');
  });

  it('should show the password error when password length is less than 12', () => {
    cy.get('input[id="password"]').type('short', { force: true });

    cy.get('[data-testid=passwordError]')
      .should('exist')
      .contains('Password must');
  });

  it('should show the password error when password do not contain lowercase', () => {
    cy.get('input[id="password"]').type('UPPERCASE_10_!', { force: true });

    cy.get('[data-testid=passwordError]')
      .should('exist')
      .contains('Password must');
  });

  it('should show the password error when password do not contain uppercase', () => {
    cy.get('input[id="password"]').type('lowercase_10_!', { force: true });

    cy.get('[data-testid=passwordError]')
      .should('exist')
      .contains('Password must');
  });

  it('should not show the password error when password is valid', () => {
    cy.get('input[id="password"]').type('UP_lowercase_10_!', { force: true });

    cy.get('[data-testid=passwordError]').should('not.exist');
  });

  it('should show the password error when password do not match', () => {
    cy.get('input[id="password"]').type('UP_lowercase_10_!', { force: true });

    cy.get('input[id="confirmPassword"]').type('UP_lowercase_11_!', {
      force: true,
    });

    cy.get('[data-testid=confirmPasswordError]')
      .should('exist')
      .contains('Passwords do not match');
  });

  it('should show the terms and condition error when terms are not accepted', () => {
    cy.get('input[id="agreeToTerms"]').should('exist');
    cy.get('button[id="sign-up-button"]').click();

    cy.get('[data-testid=agreeToTermsError]')
      .should('exist')
      .contains('You must accept the terms and conditions.');
  });

  it('should show the captcha error when is not accepted', () => {
    cy.get('iframe[title="reCAPTCHA"]').should('exist');
    cy.get('button[id="sign-up-button"]').click();

    cy.get('[data-testid=reCaptchaError]')
      .should('exist')
      .contains('You must verify you are not a robot.');
  });
});
