import './commands';

declare global {
  namespace Cypress {
    interface Chainable {
      /**
       * Dispatches loginSuccess action to the store with the given user profile
       * Simulates the login of a user
       * @param email email of the user to inject
       */
      injectAuthenticatedUser(email: string): void;

      /**
       * Selects a dropdown item in a MUI dropdown
       * @param elementKey selector of the dropdown element
       * @param dropDownDataValue data value of the dropdown item to select
       */
      muiDropdownSelect(elementKey: string, dropDownDataValue: string): void;

      /**
       * Tests if an element has the MUI error
       * @param elementKey selector of the element to assert the MUI error class
       */
      assetMuiError(elementKey: string): void;

      /**
       * Wipes the firebase auth state, creates a user and signs in. Injects the user into the store
       * @param email email of the new user
       * @param password password of the new user
       */
      createNewUserAndSignIn(email: string, password: string): void;
    }
  }
}
