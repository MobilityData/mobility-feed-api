import { app } from '../../firebase';
import { type User } from '../types';

/**
 * Send an email verification to the current user.
 * This function does nothing if the user is not logged in or if the email is already verified.
 */
export const sendEmailVerification = async (): Promise<void> => {
  try {
    const user = app.auth().currentUser;
    if (user !== null && !user.emailVerified) {
      await user.sendEmailVerification();
    }
  } catch (error) {
    // Nothing to do if the email verification fails
    // eslint-disable-next-line no-console
    console.log(error);
  }
};

/**
 * Return the current user or null if the user is not logged in.
 */
export const getUserFromSession = (): User | null => {
  const currentUser = app.auth().currentUser;
  if (currentUser === null) {
    return null;
  }
  return {
    fullname: currentUser?.displayName ?? undefined,
    email: currentUser?.email ?? '',
    // Organization cannot be retrieved from the current user
    organization: undefined,
  };
};

export const getUserOrganization = async (): Promise<string> => {
  throw new Error('Not implemented');
};

export const saveOrganization = async (): Promise<string> => {
  throw new Error('Not implemented');
};
