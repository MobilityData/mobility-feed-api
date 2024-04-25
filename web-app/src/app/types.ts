import {
  GithubAuthProvider,
  GoogleAuthProvider,
  OAuthProvider,
} from 'firebase/auth';

export type ChildrenElement =
  | string
  | JSX.Element
  | JSX.Element[]
  | (() => JSX.Element);

export interface EmailLogin {
  email: string;
  password: string;
}

export interface User {
  fullName?: string;
  email?: string;
  organization?: string;
  accessToken?: string;
  accessTokenExpirationTime?: string;
  refreshToken?: string;
  isRegistered: boolean;
  isRegisteredToReceiveAPIAnnouncements: boolean;
  isEmailVerified: boolean;
  isAnonymous: boolean;
}

export interface UserData {
  fullName: string;
  organization?: string;
  isRegisteredToReceiveAPIAnnouncements: boolean;
}

export const USER_PROFILE = 'userProfile';

export const USER_PROFILE_LOGIN = `${USER_PROFILE}/login`;
export const USER_PROFILE_LOGIN_SUCCESS = `${USER_PROFILE}/loginSuccess`;
export const USER_PROFILE_LOGIN_FAIL = `${USER_PROFILE}/loginFail`;
export const USER_PROFILE_LOGOUT = `${USER_PROFILE}/logout`;
export const USER_PROFILE_LOGOUT_SUCCESS = `${USER_PROFILE}/logoutSuccess`;
export const USER_PROFILE_SIGNUP = `${USER_PROFILE}/signUp`;
export const USER_PROFILE_SEND_VERIFICATION_EMAIL = `${USER_PROFILE}/verifyEmail`;
export const USER_REQUEST_REFRESH_ACCESS_TOKEN = `${USER_PROFILE}/requestRefreshAccessToken`;
export const USER_PROFILE_LOAD_ORGANIZATION_FAIL = `${USER_PROFILE}/loadOrganizationFail`;
export const USER_PROFILE_LOGIN_WITH_PROVIDER = `${USER_PROFILE}/loginWithProvider`;
export const USER_PROFILE_CHANGE_PASSWORD = `${USER_PROFILE}/changePassword`;
export const USER_PROFILE_REFRESH_INFORMATION = `${USER_PROFILE}/refreshUserInformation`;
export const USER_PROFILE_RESET_PASSWORD = `${USER_PROFILE}/resetPassword`;
export const USER_PROFILE_ANONYMOUS_LOGIN = `${USER_PROFILE}/anonymousLogin`;

export const FEED_PROFILE = 'feedProfile';

export const FEED_PROFILE_UPDATE_FEED_ID = `${FEED_PROFILE}/updateFeedId`;
export const FEED_PROFILE_LOADING_FEED = `${FEED_PROFILE}/loadingFeed`;
export const FEED_PROFILE_LOADING_FEED_SUCCESS = `${FEED_PROFILE}/loadingFeedSuccess`;
export const FEED_PROFILE_LOADING_FEED_FAIL = `${FEED_PROFILE}/loadingFeedFail`;

export enum ErrorSource {
  SignUp = 'SignUp',
  Login = 'Login',
  Logout = 'Logout',
  RefreshingAccessToken = 'RefreshingAccessToken',
  ChangePassword = 'ChangePassword',
  Registration = 'Registration',
  ResetPassword = 'ResetPassword',
  VerifyEmail = 'VerifyEmail',
  DatabaseAPI = 'DatabaseAPI',
}

export interface AppError {
  code: string | 'unknown';
  message: string;
  source?: ErrorSource;
}

export type AppErrors = {
  [Property in ErrorSource]: AppError | null;
};

export enum OauthProvider {
  Google = 'Google',
  Github = 'Github',
  Apple = 'Apple',
}

export const oathProviders = {
  Google: new GoogleAuthProvider(),
  Github: new GithubAuthProvider(),
  Apple: new OAuthProvider('apple.com'),
};
