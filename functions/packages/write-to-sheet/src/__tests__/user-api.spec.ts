// import {
//   retrieveUser,
//   updateUserInformation,
//   retrieveUserInformation}
//   from "../impl/user-api-impl";
// import {Datastore} from "@google-cloud/datastore";
// import {CallableRequest, HttpsError} from "firebase-functions/v2/https";
//
// jest.mock("@google-cloud/datastore");
//
// describe("retrieveUser", () => {
//   it("should retrieve a user by uid", async () => {
//     const mockUid = "testUid";
//     const mockUser = {
//       uid: mockUid,
//       fullName: "Test User",
//       organization: "Test Org",
//     };
//
//     // mocking the Datastore query
//     Datastore.prototype.createQuery = jest.fn().mockReturnValue({
//       filter: jest.fn().mockReturnThis(),
//       limit: jest.fn().mockReturnThis(),
//       run: jest.fn().mockResolvedValue([[mockUser]]),
//     });
//     const mockDatastore = new Datastore();
//
//     const result = await retrieveUser(mockDatastore, mockUid);
//     expect(result).toEqual(mockUser);
//   });
// });
//
// describe("retrieveUserInformation", () => {
//   it("should throw an error if uid is not provided", async () => {
//     const mockRequest = {
//       auth: {uid: undefined},
//       rawRequest: {},
//     };
//     await expect(
//       retrieveUserInformation(mockRequest as unknown as CallableRequest))
//       .rejects
//       .toThrow(HttpsError);
//   });
// });
//
// describe("updateUserInformation", () => {
//   beforeEach(() => {
//     jest.mock("../impl/user-api-impl.ts", () => ({
//       retrieveUserKey: jest.fn().mockResolvedValue("userKey"),
//     }));
//     Datastore.prototype.save = jest.fn().mockReturnValue({
//       catch: jest.fn().mockReturnThis(),
//     });
//   });
//
//   it("should update user information", async () => {
//     const mockRequest = {
//       auth: {uid: "testUid"},
//       data: {fullName: "Test User", organization: "Test Org"},
//       rawRequest: {},
//     };
//     const result = await updateUserInformation(mockRequest as CallableRequest);
//     expect(result).toEqual("User testUid updated successfully.");
//   });
//
//   it("should update user information if organization is undefined",
//     async () => {
//       const mockRequest = {
//         auth: {uid: "testUid"},
//         data: {fullName: "Test User", organization: undefined},
//         rawRequest: {},
//       };
//       const result =
//         await updateUserInformation(mockRequest as CallableRequest);
//       expect(result).toEqual("User testUid updated successfully.");
//     });
//
//   it("should throw an error if uid is not provided", async () => {
//     const mockRequest = {
//       auth: {uid: undefined},
//       data: {fullName: "Test User", organization: "Test Org"},
//       rawRequest: {},
//     };
//     await expect(
//       updateUserInformation(mockRequest as unknown as CallableRequest))
//       .rejects
//       .toThrow(HttpsError);
//   });
//
//   it("should throw an error if fullName is not provided", async () => {
//     const mockRequest = {
//       auth: {uid: "testUid"},
//       data: {fullName: undefined, organization: "Test Org"},
//       rawRequest: {},
//     };
//     await expect(
//       updateUserInformation(mockRequest as unknown as CallableRequest))
//       .rejects
//       .toThrow(HttpsError);
//   });
//   it("should throw an HttpsError when save throws an error", async () => {
//     const mockRequest = {
//       auth: {uid: "testUid"},
//       data: {fullName: "Test User", organization: "Test Org"},
//       rawRequest: {},
//     };
//
//     Datastore.prototype.save = jest.fn().mockImplementation(() => {
//       throw new Error("Datastore save error");
//     });
//
//     await expect(
//       updateUserInformation(mockRequest as unknown as CallableRequest))
//       .rejects
//       .toThrow(HttpsError);
//
//     await expect(
//       updateUserInformation(mockRequest as unknown as CallableRequest))
//       .rejects
//       .toThrow(new HttpsError("internal", "Unable to update user information"));
//   });
// });
