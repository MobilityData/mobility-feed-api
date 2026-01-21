'use client';

import { useEffect, type ReactElement } from 'react';
import { app } from '../../firebase';
import { setAuthTokenAction } from '../actions/auth-actions';

export default function AuthTokenSync(): ReactElement | null {
  useEffect(() => {
    // Sets the auth token in a httpOnly cookie for server side requests
    // Uses Next.js const cookieStore = await cookies(); for cookie management
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
