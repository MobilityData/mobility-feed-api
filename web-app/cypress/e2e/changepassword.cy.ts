const email = Cypress.env('email');
console.log(Cypress.env('email'));
const currentPassword = Cypress.env('currentPassword');
const newPassword = Cypress.env('newPassword');
describe('Change Password Screen', () => {
  before(() => {});

  beforeEach(() => {
    // Visit the login page and login
    cy.visit('/sign-in');
    cy.get('input[id="email"]').clear().type(email);
    cy.get('input[id="password"]').clear().type(currentPassword);
    cy.get('button[type="submit"]').click();
    // Wait for the user to be redirected to the home page
    cy.location('pathname').should('eq', '/account');
    // Visit the change password page
    cy.visit('/change-password');
  });

  it('should render components', () => {
    // Check that the current password field exists
    cy.get('input[id="currentPassword"]').should('exist');

    // Check that the new password field exists
    cy.get('input[id="newPassword"]').should('exist');

    // Check that the confirm new password field exists
    cy.get('input[id="confirmNewPassword"]').should('exist');
  });

  it('should show error when current password is incorrect', () => {
    // Type the wrong current password
    cy.get('input[id="currentPassword"]').type('wrong');

    // Type the new password
    cy.get('input[id="newPassword"]').type(newPassword);

    // Confirm the new password
    cy.get('input[id="confirmNewPassword"]').type(newPassword);

    // Submit the form
    cy.get('button[type="submit"]').click();

    // Check that the error message is displayed
    cy.contains(
      'The password is invalid or the user does not have a password. (auth/wrong-password).',
    ).should('exist');
  });

  it('should change password', () => {
    // Type the current password
    cy.get('input[id="currentPassword"]').type(currentPassword);

    // Type the new password
    cy.get('input[id="newPassword"]').type(newPassword);

    // Confirm the new password
    cy.get('input[id="confirmNewPassword"]').type(newPassword);

    // Submit the form
    cy.get('button[type="submit"]').click();

    // Check that the password was changed successfully
    // This depends on how your application shows that the password was changed successfully
    // For example, you might check for a success message or that you're redirected to a certain page
    cy.contains('Change Password Succeeded').should('exist');
    cy.get('[cy-data="goToAccount"]').click();
    cy.location('pathname').should('eq', '/account');

    // Reset the password back to the original password
    cy.visit('/change-password');
    cy.get('input[id="currentPassword"]').type(newPassword);
    cy.get('input[id="newPassword"]').type(currentPassword);
    cy.get('input[id="confirmNewPassword"]').type(currentPassword);
    cy.get('button[type="submit"]').click();
    cy.contains('Change Password Succeeded').should('exist');
  });
});
