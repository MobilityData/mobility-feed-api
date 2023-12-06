describe('Change Password Screen', () => {
  beforeEach(() => {
    cy.visit('/change-password');
  });

  it('should render components', () => {
    cy.get('input[id="currentPassword"]').should('exist');
    cy.get('input[id="newPassword"]').should('exist');
    cy.get('input[id="confirmNewPassword"]').should('exist');
  });
});
