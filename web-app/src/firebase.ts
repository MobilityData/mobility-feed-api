import firebase from 'firebase/compat/app';
import { getRemoteConfig } from 'firebase/remote-config';

const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY,
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID,
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.REACT_APP_FIREBASE_APP_ID,
};

export const app = firebase.initializeApp(firebaseConfig);
export const remoteConfig = getRemoteConfig(app);
remoteConfig.defaultConfig = {
  enable_google_sso_login: true,
};
