/**
 * Import function triggers from their respective submodules:
 *
 * import {onCall} from "firebase-functions/v2/https";
 * import {onDocumentWritten} from "firebase-functions/v2/firestore";
 *
 * See a full list of supported triggers at https://firebase.google.com/docs/functions
 */
import {initializeApp} from "firebase-admin/app";
import {onCall} from "firebase-functions/v2/https";
import * as logger from "firebase-functions/logger";

// Start writing functions
// https://firebase.google.com/docs/functions/typescript
initializeApp();

// export const helloWorld = onRequest((request, response) => {
//   logger.info("Hello logs!", {structuredData: true});
//   request.headers.a
//   const simpleRequest = {
//     method: request.method,
//     url: request.url,
//     headers: request.headers,
//     other: request.url,
//     // Add other properties as needed
//   };
//   //   response.send(`Hello from Firebase 2 ${request.auth.uid}!`);
//   response.send(simpleRequest);
// });

export const helloWorld2 = onCall(
  {minInstances: 10, invoker: "public", cors: "*"},
  (request) => {
    logger.info(request.auth);
    return "Hello";
  });
