import {initializeApp} from "firebase-admin/app";
import {CallableRequest, onCall} from "firebase-functions/v2/https";
import * as userAPI from "./impl/user-api-impl";


initializeApp();

export const updateUserInformation = onCall(
  {minInstances: 0, maxInstances: 100, invoker: "public", cors: "*"},
  /**
     * Updates or creates instance of user's information in Datastore
     * @param {CallableRequest} request
     * @return {Promise<string>} Success message
     * @throws {HttpsError} Throws an error if the user is not authenticated,
     * full name is not provided or if there is an error updating the user
     */
  async (request: CallableRequest): Promise<string> => {
    return await userAPI.updateUserInformation(request);
  });

export const retrieveUserInformation = onCall(
  {minInstances: 0, maxInstances: 100, invoker: "public", cors: "*"},
  /**
     * Validates if the user is registered in the datastore
     * @param {CallableRequest} request - The callable request containing the
     * user authentication data
     * @return {Promise<Entity | undefined>} The user information from the
     * datastore
     * @throws {HttpsError} Throws an error if the user is not authenticated
     */
  async (request: CallableRequest): Promise<string> => {
    return await userAPI.retrieveUserInformation(request);
  });
