import {initializeApp} from "firebase-admin/app";
import {onRequest} from "firebase-functions/v2/https";
import * as feedAPI from "./impl/feed-form-impl";
import {defineSecret} from "firebase-functions/params";
const googleSheetSpreadsheetId = defineSecret("GOOGLE_SHEET_SPREADSHEET_ID");
const googleSheetServiceEmail = defineSecret("GOOGLE_SHEET_SERVICE_EMAIL");
const googleSheetPrivateKey = defineSecret("GOOGLE_SHEET_PRIVATE_KEY");

initializeApp();

export const writeToSheet = onRequest(
  {
    minInstances: 0,
    maxInstances: 100,
    invoker: "public",
    cors: "*",
    region: "northamerica-northeast1",
    secrets: [
      googleSheetSpreadsheetId,
      googleSheetServiceEmail,
      googleSheetPrivateKey,
    ],
  },
  async (request, response) => {
    const secrets = {
      sheetId: googleSheetSpreadsheetId.value(),
      serviceEmail: googleSheetServiceEmail.value(),
      // On private key it's stored in a strange format, so we need to format it
      // Other solution would be to base64 encode it and decode it here
      privateKey: googleSheetPrivateKey.value().replace(/\\n/g, "\n"),
    };
    await feedAPI.writeToSheet(request, response, secrets);
  }
);
