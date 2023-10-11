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
  fullname?: string;
  email: string;
  organization?: string;
}

export const USER_PROFILE = 'userProfile';

export const USER_PROFILE_LOGIN = `${USER_PROFILE}/login`;
export const USER_PROFILE_LOGIN_SUCCESS = `${USER_PROFILE}/loginSuccess`;
export const USER_PROFILE_LOGIN_FAIL = `${USER_PROFILE}/loginFail`;
export const USER_PROFILE_LOGOUT = `${USER_PROFILE}/logout`;
export const USER_PROFILE_LOGOUT_SUCCESS = `${USER_PROFILE}/logoutSuccess`;
export const USER_PROFILE_SIGNUP = `${USER_PROFILE}/signUp`;
export const USER_PROFILE_SIGNUP_SUCCESS = `${USER_PROFILE}/signUpSuccess`;
export const USER_PROFILE_SIGNUP_FAIL = `${USER_PROFILE}/signUpFail`;
export const USER_PROFILE_LOAD_ORGANIZATION = `${USER_PROFILE}/loadOrganization`;
export const USER_PROFILE_LOAD_ORGANIZATION_SUCCESS = `${USER_PROFILE}/loadOrganizationSuccess`;

export enum ErrorSource {
  SignUp = 'SignUp',
  Login = 'Login',
  Logout = 'Logout',
}

export interface AppError {
  code: string | 'unknown';
  message: string;
  source?: ErrorSource;
}

export type AppErrors = {
  [Property in ErrorSource]: AppError | null;
};
