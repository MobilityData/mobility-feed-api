import { type AdditionalUserInfo } from 'firebase/auth';
import { app } from '../../firebase';
import { type User, type UserData } from '../types';
import { getFunctions, httpsCallable } from 'firebase/functions';

/**
 * Send an email verification to the current user.
 */
export const sendEmailVerification = async (): Promise<void> => {
  const user = app.auth().currentUser;
  if (user !== null && !user.emailVerified) {
    await user.sendEmailVerification();
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
    fullName: currentUser?.displayName ?? undefined,
    email: currentUser?.email ?? '',
    isRegistered: false,
    isEmailVerified: currentUser?.emailVerified ?? false,
    // Organization cannot be retrieved from the current user
    organization: undefined,
    isRegisteredToReceiveAPIAnnouncements: false,
    isAnonymous: currentUser.isAnonymous,
    refreshToken,
  };
};

export const generateUserAccessToken = async (
  user: User,
): Promise<User | null> => {
  const currentUser = app.auth().currentUser;

  if (currentUser === null) {
    return null;
  }
  const refreshToken = currentUser.refreshToken;
  const idTokenResult = await currentUser.getIdTokenResult(true);
  const accessToken = idTokenResult.token;
  const accessTokenExpirationTime = idTokenResult.expirationTime;

  return {
    ...user,
    refreshToken,
    accessToken,
    accessTokenExpirationTime,
  };
};

export const updateUserInformation = async (data: {
  fullName: string | undefined;
  organization: string | undefined;
  isRegisteredToReceiveAPIAnnouncements: boolean;
}): Promise<void> => {
  const functions = getFunctions(app, 'northamerica-northeast1');
  const updateUserInformation = httpsCallable(
    functions,
    'updateUserInformation',
  );
  await updateUserInformation({
    fullName: data.fullName,
    organization: data.organization,
    isRegisteredToReceiveAPIAnnouncements:
      data.isRegisteredToReceiveAPIAnnouncements,
  });
};

export const retrieveUserInformation = async (): Promise<
  UserData | undefined
> => {
  const functions = getFunctions(app, 'northamerica-northeast1');
  const retrieveUserInformation = httpsCallable(
    functions,
    'retrieveUserInformation',
  );
  const user = await retrieveUserInformation();
  if (user !== undefined) {
    return user.data as UserData;
  }
  return undefined;
};

export const populateUserWithAdditionalInfo = (
  user: User,
  userData: UserData | undefined,
  additionalUserInfo: AdditionalUserInfo | undefined,
): User => {
  return {
    ...user,
    isRegistered: userData !== null,
    fullName:
      userData?.fullName ??
      (additionalUserInfo?.profile?.name as string) ??
      undefined,
    organization: userData?.organization ?? undefined,
    email:
      user?.email ??
      (additionalUserInfo?.profile?.email as string) ??
      undefined,
    isRegisteredToReceiveAPIAnnouncements:
      userData?.isRegisteredToReceiveAPIAnnouncements ?? false,
  };
};
