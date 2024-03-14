import firebase from 'firebase/compat/app';
import 'firebase/compat/remote-config';

const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY,
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID,
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.REACT_APP_FIREBASE_APP_ID,
};

export const app = firebase.initializeApp(firebaseConfig);
export const remoteConfig = firebase.remoteConfig();
remoteConfig.settings.minimumFetchIntervalMillis = Number(
  process.env.REMOTE_CONFIG_MINIMUM_FETCH_INTERVAL_MILLIS ?? 3600000, // default to 12 hours
);
