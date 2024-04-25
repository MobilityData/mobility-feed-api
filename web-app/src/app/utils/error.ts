import { type FeedError, type ProfileError } from '../types';
import { FirebaseError } from '@firebase/util';

export const getAppError = (error: unknown): ProfileError | FeedError => {
  const appError: ProfileError | FeedError = {
    code: 'unknown',
    message: 'Unknown error',
  };
  if (error instanceof FirebaseError) {
    appError.code = error.code;
    let message = error.message;
    if (error.message.startsWith('Firebase: ')) {
      message = error.message.substring('Firebase: '.length);
    }
    appError.message = message;
  } else {
    appError.message = `${error as string}`;
  }
  return appError;
};
