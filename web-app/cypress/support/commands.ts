// eslint-disable-next-line @typescript-eslint/triple-slash-reference
/// <reference types="cypress" />
// ***********************************************
// This example commands.ts shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
// -- This is a parent command --
// Cypress.Commands.add('login', (email, password) => { ... })
//
//
// -- This is a child command --
// Cypress.Commands.add('drag', { prevSubject: 'element'}, (subject, options) => { ... })
//
//
// -- This is a dual command --
// Cypress.Commands.add('dismiss', { prevSubject: 'optional'}, (subject, options) => { ... })
//
//
// -- This will overwrite an existing command --
// Cypress.Commands.overwrite('visit', (originalFn, url, options) => { ... })
//
// declare global {
//   namespace Cypress {
//     interface Chainable {
//       login(email: string, password: string): Chainable<void>
//       drag(subject: string, options?: Partial<TypeOptions>): Chainable<Element>
//       dismiss(subject: string, options?: Partial<TypeOptions>): Chainable<Element>
//       visit(originalFn: CommandOriginalFn, url: string, options: Partial<VisitOptions>): Chainable<Element>
//     }
//   }
// }

Cypress.Commands.add('injectAuthenticatedUser', () => {
  cy.window()
    .its('store')
    .invoke('dispatch', {
      type: 'userProfile/loginSuccess',
      payload: {
        fullName: 'Valery',
        email: 'testuser@gmail.com',
        isRegistered: true,
        isEmailVerified: true,
        organization: '',
        isRegisteredToReceiveAPIAnnouncements: false,
        isAnonymous: false,
        refreshToken:
          'AMf-vBwvDFwWA77IKuTUdQ9eZ7sCalLb3LPfHupyvvI91SYcImb_e5R417gPIZbVJxaJUSvMDqHWlQaMMZQZkkahT9zFW3FXymDMmvSzKB-NKO2X_lw1yCP_YyegslW6Wl4y2PRG_gEyUHxpESrjDVI_scIDIvfHaoH97-GraKJFgmCo61QzmYyMY8vyaOxyH9ovcVwdiy-KLpRbU-B8VrtrRwKg-o7BWggTlIRXu5hgtG34lS8GCdM',
      },
    });
});

Cypress.Commands.add(
  'muiDropdownSelect',
  (elementKey: string, dropDownDataValue: string) => {
    cy.get('[data-testid="overlay"]', { timeout: 6000 }).should('not.exist');
    cy.get(elementKey).click();
    cy.get(`ul > li[data-value="${dropDownDataValue}"]`).click();
  },
);

Cypress.Commands.add('assetMuiError', (elementKey: string) => {
  cy.get(elementKey).should('have.class', 'Mui-error');
});
