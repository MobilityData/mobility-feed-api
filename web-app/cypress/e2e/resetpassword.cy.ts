describe('Reset Password Screen', () => {
  beforeEach(() => {
    cy.visit('/forgot-password');
  });

  it('should render components', () => {
    cy.get('input[id="email"]').should('exist');
  });

  it('should show error when email no email is provided', () => {
    cy.get('input[id="email"]').type('not an email', { force: true });

    cy.get('[data-testid=emailError]').should('exist');
  });

  it('should show the captcha error when is not accepted', () => {
    cy.get('iframe[title="reCAPTCHA"]').should('exist');
    cy.get('input[id="email"]').type('notvalid@e.c', { force: true });
    cy.get('[type="submit"]').click();
    cy.get('[data-testid=reCaptchaError]')
      .should('exist')
      .contains('You must verify you are not a robot.');
  });
});
