import {initializeApp} from "firebase-admin/app";
import {CallableRequest, onCall} from "firebase-functions/v2/https";
import * as feedAPI from "./impl/feed-form-impl";
import {type FeedSubmissionFormRequestBody} from "./impl/types";

initializeApp();

export const writeToSheet = onCall(
  {
    minInstances: 0,
    maxInstances: 100,
    invoker: "public",
    cors: "*",
    region: "northamerica-northeast1",
  },
  async (request: CallableRequest<FeedSubmissionFormRequestBody>) => {
    return await feedAPI.writeToSheet(request);
  }
);
