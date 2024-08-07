import {initializeApp} from "firebase-admin/app";
import {onRequest} from "firebase-functions/v2/https";
import * as feedAPI from "./impl/feed-form-impl";

initializeApp();

export const writeToSheet = onRequest(
  {
    minInstances: 0,
    maxInstances: 100,
    invoker: "public",
    cors: "*",
    region: "northamerica-northeast1",
  },
  async (request, response) => {
    await feedAPI.writeToSheet(request, response);
  }
);
