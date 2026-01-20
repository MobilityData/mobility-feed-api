import { initializeApp, getApps, cert, type App } from 'firebase-admin/app';

/**
 * Server-only Firebase Admin SDK initialization.
 * Uses Application Default Credentials (ADC) which works automatically on Cloud Run.
 * For local development, you can either:
 * 1. Run `gcloud auth application-default login`
 * 2. Set GOOGLE_APPLICATION_CREDENTIALS env var to a service account JSON path
 */

let adminApp: App | undefined;

export function getFirebaseAdminApp(): App {
  if (adminApp != undefined) {
    return adminApp;
  }

  const existingApps = getApps();
  if (existingApps.length > 0) {
    adminApp = existingApps[0];
    return adminApp;
  }

  // Check if we have explicit credentials via environment variable
  const serviceAccountJson = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;

  if (serviceAccountJson != null && serviceAccountJson.length > 0) {
    try {
      const serviceAccount = JSON.parse(serviceAccountJson);
      adminApp = initializeApp({
        credential: cert(serviceAccount),
        projectId: serviceAccount.project_id,
      });
    } catch (error) {
      console.error('Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON:', error);
      // Fall through to ADC
    }
  }

  if (adminApp == undefined) {
    // Use Application Default Credentials (works on Cloud Run automatically)
    adminApp = initializeApp({
      projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    });
  }

  return adminApp;
}
