'use server';

import { cookies } from 'next/headers';

export async function setAuthTokenAction(token: string | null): Promise<void> {
  const cookieStore = await cookies();

  if (token != null && token.length > 0) {
    // We assume the toke is valid -> could add extra layer of security but will make an extra call to Firebase
    // If bad token is provided, it will be rejected by external API
    cookieStore.set('firebase_token', token, {
      path: '/',
      maxAge: 3600,
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
    });
  } else {
    cookieStore.set('firebase_token', '', {
      path: '/',
      maxAge: 0,
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
    });
  }
}
