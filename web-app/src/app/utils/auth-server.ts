import { cookies } from 'next/headers';
import { app } from '../../firebase';
import firebase from 'firebase/compat/app';
import 'firebase/compat/auth';
// TODO: for anonymous auth use fireabse admin

/**
 * Retrieves the Firebase access token from the 'firebase_token' cookie.
 * If the cookie is missing, performs a server-side anonymous login to generate a token.
 * This ensures SSR pages can access the API even for direct, unauthenticated visits.
 */
export async function getSSRAccessToken(): Promise<string> {
  const cookieStore = await cookies();
  const tokenCookie = cookieStore.get('firebase_token');

  if (tokenCookie?.value != null && tokenCookie.value.length > 0) {
    try {
      // Basic JWT decoding to check expiry
      const token = tokenCookie.value;
      const payloadBase64 = token.split('.')[1];
      const payload = JSON.parse(
        Buffer.from(payloadBase64, 'base64').toString(),
      );
      const now = Math.floor(Date.now() / 1000);

      if (payload.exp != null && payload.exp > now) {
        return token;
      }
    } catch (error) {}
  }

  // Fallback: Server-side Anonymous Login
  // We use NONE persistence to verify we don't store this session in any shared environment storage
  try {
    const auth = app.auth();
    await auth.setPersistence(firebase.auth.Auth.Persistence.NONE);
    const userCredential = await auth.signInAnonymously();
    if (userCredential.user != null) {
      const token = await userCredential.user.getIdToken();
      return token;
    }
  } catch (error) {}

  return '';
}
