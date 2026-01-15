'use client';

import { useEffect } from 'react';
import { app } from '../../firebase';
import { useDispatch } from 'react-redux';
import { setAuthTokenAction } from '../actions/auth-actions';

export default function AuthTokenSync() {
  const dispatch = useDispatch();
  useEffect(() => {
    // Listen for token changes
    const unsubscribe = app.auth().onIdTokenChanged(async (user) => {
      if (user) {
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
