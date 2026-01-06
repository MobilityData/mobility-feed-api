import firebase from 'firebase/compat/app';
import 'firebase/compat/remote-config';
import 'firebase/compat/auth';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export const app = firebase.initializeApp(firebaseConfig);
export const remoteConfig =
  typeof window !== 'undefined' ? firebase.remoteConfig() : ({} as any);

if (typeof window !== 'undefined') {
  remoteConfig.settings.minimumFetchIntervalMillis = Number(
    process.env.NEXT_PUBLIC_REMOTE_CONFIG_MINIMUM_FETCH_INTERVAL_MILLI ??
      3600000, // default to 12 hours
  );
}

if (typeof window !== 'undefined' && (window as any).Cypress) {
  app.auth().useEmulator('http://localhost:9099/');
}
