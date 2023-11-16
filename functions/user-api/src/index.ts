import {initializeApp} from "firebase-admin/app";
import {onCall} from "firebase-functions/v2/https";
import * as userAPI from "./impl/user-api-impl";


initializeApp();

export const updateUserInformation = onCall(
  {minInstances: 0, maxInstances: 100, invoker: "public", cors: "*"},
  async (request) => {
    /**
     * Updates or creates instance of user's information in Datastore
     * @param request
     */
    return await userAPI.updateUserInformation(request);
  });

export const retrieveUserInformation = onCall(
  {minInstances: 0, maxInstances: 100, invoker: "public", cors: "*"},
  async (request) => {
    /**
     * Validates if the user is registered in the datastore
     * @param request
     */
    return await userAPI.retrieveUserInformation(request);
  });
