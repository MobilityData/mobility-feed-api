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

export const FEEDS_RESET_FEEDS = `feeds/resetFeeds`;
export const FEEDS_LOADING_FEEDS = `feeds/loadingFeeds`;
export const FEEDS_LOADING_FEEDS_SUCCESS = `feeds/loadingFeedsSuccess`;
export const FEEDS_LOADING_FEEDS_FAIL = `feeds/loadingFeedsFail`;

export const DATASET_UPDATE_FEED_ID = `dataset/updateDatasetId`;
export const DATASET_LOADING_FEED = `dataset/loadingDataset`;
export const DATASET_LOADING_FEED_SUCCESS = `dataset/loadingDatasetSuccess`;
export const DATASET_LOADING_FEED_FAIL = `dataset/loadingDatasetFail`;

export enum ProfileErrorSource {
  SignUp = 'SignUp',
  Login = 'Login',
  Logout = 'Logout',
  RefreshingAccessToken = 'RefreshingAccessToken',
  ChangePassword = 'ChangePassword',
  Registration = 'Registration',
  ResetPassword = 'ResetPassword',
  VerifyEmail = 'VerifyEmail',
}
export enum FeedErrorSource {
  DatabaseAPI = 'DatabaseAPI',
}

export interface ProfileError {
  code: string | 'unknown';
  message: string;
  source?: ProfileErrorSource;
}

export interface FeedError {
  code: string | 'unknown';
  message: string;
  source?: FeedErrorSource;
}

export type ProfileErrors = {
  [Property in ProfileErrorSource]: ProfileError | null;
};

export type FeedsErrors = {
  [Property in FeedErrorSource]: FeedError | null;
};

export type FeedErrors = {
  [Property in FeedErrorSource]: FeedError | null;
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
