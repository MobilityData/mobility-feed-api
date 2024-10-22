const currentPassword = 'IloveOrangeCones123!';
const newPassword = currentPassword + 'TEST';
const email = 'cypressTestUser@mobilitydata.org';

describe('Change Password Screen', () => {
  beforeEach(() => {
    cy.visit('/');
    cy.get('[data-testid="home-title"]').should('exist');
    cy.createNewUserAndSignIn(email, currentPassword);
    cy.get('[data-cy="accountHeader"]').should('exist'); // assures that the user is signed in
    cy.visit('/change-password');
  });

  it('should render components', () => {
    cy.get('input[id="currentPassword"]').should('exist');
    cy.get('input[id="newPassword"]').should('exist');
    cy.get('input[id="confirmNewPassword"]').should('exist');
  });

  it('should show error when current password is incorrect', () => {
    cy.get('input[id="currentPassword"]').type('wrong');
    cy.get('input[id="newPassword"]').type(newPassword);
    cy.get('input[id="confirmNewPassword"]').type(newPassword);
    cy.get('button[type="submit"]').click();
    cy.contains(
      'The password is invalid or the user does not have a password. (auth/wrong-password).',
    ).should('exist');
  });

  it('should change password', () => {
    cy.intercept('POST', '/retrieveUserInformation', {
      statusCode: 200,
      body: {
        result: {
          uid: 'ep4EwJvgNhfEER152EfzLSI0MBG2',
          isRegisteredToReceiveAPIAnnouncements: false,
          organization: '',
          fullName: 'Alessandro',
          registrationCompletionTime: '2024-09-24T15:34:55.381Z',
        },
      },
    });
    cy.get('input[id="currentPassword"]').type(currentPassword);
    cy.get('input[id="newPassword"]').type(newPassword);
    cy.get('input[id="confirmNewPassword"]').type(newPassword);
    cy.get('button[type="submit"]').click();

    cy.contains('Change Password Succeeded').should('exist');
    cy.get('[cy-data="goToAccount"]').click();
    cy.location('pathname').should('eq', '/account');

    // logout
    cy.get('[data-cy="signOutButton"]').click();
    cy.get('[data-cy="confirmSignOutButton"]').should('exist').click();
    cy.visit('/sign-in');
    cy.get('[data-cy="signInEmailInput"]').type(email);
    cy.get('[data-cy="signInPasswordInput"]').type(newPassword);
    cy.get('[data-testid="signin"]').click();
    cy.location('pathname').should('eq', '/account');
  });
});
