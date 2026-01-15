'use client';

import { useEffect } from 'react';
import { app } from '../../firebase';
import { setAuthTokenAction } from '../actions/auth-actions';

export default function AuthTokenSync(): JSX.Element | null {
  useEffect(() => {
    // Listen for token changes
    const unsubscribe = app.auth().onIdTokenChanged(async (user) => {
      if (user != null) {
        const token = await user.getIdToken();
        await setAuthTokenAction(token);
      } else {
        await setAuthTokenAction(null);
      }
    });

    return () => {
      unsubscribe();
    };
  }, []);

  return null;
}
