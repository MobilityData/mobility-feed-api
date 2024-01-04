export const passwordValidationRegex =
  /^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[$*.[\]{}()?"!@#%&/\\,><':;|_~`-])(?=.{12,})/;

export const passwordValidationError = (
  <div>
    Password must
    <ul style={{ marginTop: 0, paddingLeft: '15px' }}>
      <li>Contain at least one uppercase letter</li>
      <li>Contain at least one lowercase letter</li>
      <li>Contain at least one digit</li>
      <li>
        Contain at least one special char
        {'(^ $ * . [ ] { } ( ) ? " ! @ # % & / \\ , > < \' : ; | _ ~ `)'}
      </li>
      <li>Be at least 12 chars long</li>
    </ul>
  </div>
);
