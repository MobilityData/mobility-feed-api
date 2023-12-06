import { type AppError } from '../types';
import { FirebaseError } from '@firebase/util';

export const getAppError = (error: unknown): AppError => {
  const appError: AppError = {
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
