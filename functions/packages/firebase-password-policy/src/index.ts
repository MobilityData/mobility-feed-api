import {initializeApp} from "firebase-admin/app";
import {CallableRequest, onCall} from "firebase-functions/v2/https";


initializeApp();

export const testHelloWorld = onCall(
  {minInstances: 0, maxInstances: 100, invoker: "public"},
  /**
     * Updates or creates instance of user's information in Datastore
     * @param {CallableRequest} request
     * @return {Promise<string>} Success message
     * @throws {HttpsError} Throws an error if the user is not authenticated,
     * full name is not provided or if there is an error updating the user
     */
  async (request: CallableRequest): Promise<string> => {
    return "Hello World";
  });
