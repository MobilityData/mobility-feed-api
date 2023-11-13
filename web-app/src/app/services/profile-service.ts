import {
  updateProfile,
  type AdditionalUserInfo,
  updateCurrentUser,
} from 'firebase/auth';
import { app } from '../../firebase';
import { type OauthProvider, type User } from '../types';
import { onAuthStateChanged } from 'firebase/auth';

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
export const getUserFromSession = async (): Promise<User | null> => {
  const currentUser = app.auth().currentUser;
  if (currentUser === null) {
    return null;
  }
  const refreshToken = currentUser.refreshToken;
  return {
    fullname: currentUser?.displayName ?? undefined,
    email: currentUser?.email ?? '',
    // Organization cannot be retrieved from the current user
    organization: undefined,
    refreshToken,
  };
};

export const generateUserAccessToken = async (): Promise<User | null> => {
  // FIXME: currentUser is always null on the first call.
  // It works on the second call.
  // See https://firebase.google.com/docs/auth/web/manage-users#get_the_currently_signed-in_user
  // > Note: currentUser might also be null because the auth object has not finished initializing.
  // > If you use an observer to keep track of the user's sign-in status, you don't need to handle this case.

  // Below is a workaround to make it work.
  // app.auth();
  // await new Promise((resolve) => setTimeout(resolve, 1000));

  // The better fix would be to use the onAuthStateChanged callback.
  /*
  app.auth().onAuthStateChanged((user) => {
    if (user) {
      console.log('User is signed in.');
    } else {
      console.log('No user is signed in.');
    }
  } */
  // I suggest to use the check above to test if the user is logged in, and update userProfileSlice accordingly.
  // When the user is no longer logged in, we should redirect to the login page.
  let currentUser = app.auth().currentUser;
  if (currentUser === null) {
    return null;
  }
  const refreshToken = currentUser.refreshToken;

  const idTokenResult = await currentUser.getIdTokenResult(true);
  const accessToken = idTokenResult.token;
  const accessTokenExpirationTime = idTokenResult.expirationTime;

  app.auth().onAuthStateChanged((user) => {
    if (user != null) {
      // User is signed in
      currentUser = user;
    } else {
      // User is signed out
      console.log('User is signed out');
      // return <Navigate to='/' />;
    }
  });

  return {
    fullname: currentUser?.displayName ?? undefined,
    email: currentUser?.email ?? '',
    // Organization cannot be retrieved from the current user
    organization: undefined,
    refreshToken,
    accessToken,
    accessTokenExpirationTime,
  };
};

export const updateUserInformation = async (values: {
  fullname: string;
}): Promise<void> => {
  const currentUser = app.auth().currentUser;
  // TODO: this is to be removed and replaced by storing the information in Datastore
  if (currentUser !== null) {
    await updateProfile(currentUser, {
      displayName: values?.fullname,
    });
  }
};

export const populateUserWithAdditionalInfo = (
  user: User,
  additionalUserInfo: AdditionalUserInfo,
  oauthProvider: OauthProvider,
): User => {
  return {
    ...user,
    fullname:
      user?.fullname ??
      (additionalUserInfo.profile?.name as string) ??
      undefined,
    email:
      user?.email ?? (additionalUserInfo.profile?.email as string) ?? undefined,
  };
};
