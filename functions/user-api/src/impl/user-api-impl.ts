import {CallableRequest, HttpsError} from "firebase-functions/v2/https";
import * as logger from "firebase-functions/logger";
import {Datastore, Entity, PropertyFilter} from "@google-cloud/datastore";

const DATASTORE_USER_INFORMATION_KIND = "web_api_users";
const UID_PROPERTY_NAME = "uid";

export const retrieveUser = async (
  datastore: Datastore,
  uid: string):
  Promise<Entity | undefined> => {
  /**
   * Retrieve the user information from datastore
   * @param datastore - Datastore object
   * @param uid - The user's uid
   */
  const query =
    datastore.createQuery(DATASTORE_USER_INFORMATION_KIND)
      .filter(new PropertyFilter(UID_PROPERTY_NAME, "=", uid))
      .limit(1);
  const [users] = await query.run();
  if (users.length === 1) {
    return users[0];
  }
  return undefined;
};

export const retrieveUserKey = async (
  datastore: Datastore,
  uid: string):
  Promise<string | undefined> => {
  /**
   * Retrieve the user key from datastore
   * @param datastore - Datastore object
   * @param uid - The user's uid
   */
  const user = await retrieveUser(datastore, uid);
  if (user !== undefined) {
    return user[datastore.KEY];
  }
  return undefined;
};

export const updateUserInformation =
  async (request: CallableRequest) => {
    /**
     * Updates or creates instance of user's information in Datastore
     * @param request
     */
    const uid = request.auth?.uid ?? undefined;
    if (uid === undefined) {
      throw new HttpsError("unauthenticated",
        "Error registering the user. Verify authentication information."
      );
    }
    const fullName = request.data["fullName"] ?? undefined;
    if (fullName === undefined) {
      throw new HttpsError("invalid-argument",
        "Error registering the user. The user's full name wasn't provided."
      );
    }
    const organization = request.data["organization"] ?? undefined;
    const datastore = new Datastore();
    logger.info(`Updating user ${uid} information with ` +
      `full name ${fullName} and organization ${organization}.`);

    const userKey = await retrieveUserKey(datastore, uid) ??
      datastore.key(DATASTORE_USER_INFORMATION_KIND);

    const entity = {
      key: userKey,
      data: [
        {
          name: "uid",
          value: uid,
        },
        {
          name: "fullName",
          value: fullName,
        },
        {
          name: "organization",
          value: organization,
        },
        {
          name: "registrationCompletionTime",
          value: new Date().toJSON(),
        },
      ],
    };
    await datastore.save(entity).catch((error) => {
      throw new HttpsError("unknown", error.message);
    });
    return `User ${uid} updated successfully.`;
  };

export const retrieveUserInformation =
  async (request: CallableRequest) => {
    /**
     * Validates if the user is registered in the datastore
     * @param request
     */
    const uid = request.auth?.uid ?? undefined;
    if (uid === undefined) {
      throw new HttpsError("unauthenticated",
        "Error retrieving the user. Verify authentication information."
      );
    }
    logger.info(`Retrieving user ${uid} information.`);
    const datastore = new Datastore();
    return await retrieveUser(datastore, uid);
  };
