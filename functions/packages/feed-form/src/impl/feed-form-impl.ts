import {GoogleSpreadsheet} from "google-spreadsheet";
import {GoogleAuth} from "google-auth-library";
import * as logger from "firebase-functions/logger";
import {type FeedSubmissionFormRequestBody} from "./types";
import {type CallableRequest, HttpsError} from "firebase-functions/v2/https";
import axios from "axios";

const SCOPES = [
  "https://www.googleapis.com/auth/spreadsheets",
  "https://www.googleapis.com/auth/drive.file",
];

export const writeToSheet = async (
  request: CallableRequest<FeedSubmissionFormRequestBody>
) => {
  try {
    const uid = request.auth?.uid ?? "";
    const sheetId = process.env.FEED_SUBMIT_GOOGLE_SHEET_ID;
    if (sheetId === undefined || sheetId === "") {
      throw new HttpsError("internal", "Google Sheet ID is not defined");
    }
    const auth = new GoogleAuth({
      scopes: SCOPES,
    });
    const doc = await new GoogleSpreadsheet(sheetId, auth);
    await doc.loadInfo();
    const rawDataSheet = doc.sheetsByIndex[0];
    const formData: FeedSubmissionFormRequestBody = request.data;
    const rows = buildFeedRows(formData, uid);
    await rawDataSheet.addRows(rows, {insert: true});
    sendSlackWebhook(sheetId);
    return {message: "Data written to the new sheet successfully!"};
  } catch (error) {
    logger.error("Error writing to sheet:", error);
    throw new HttpsError(
      "internal",
      "An error occurred while writing to the sheet."
    );
  }
};

// Google sheet types that were not exportable
type RowCellData = string | number | boolean | Date;
type RawRowData = RowCellData[] | Record<string, RowCellData>;

/* eslint-disable max-len */
// Google Sheets columns titles
export enum SheetCol {
  Status = "Status",
  Timestamp = "Timestamp",
  TransitProvider = "Transit Provider",
  CurrentUrl = "Current feed URL (for feed updates)",
  DataType = "Data type",
  IssueType = "Issue type",
  DownloadUrl = "Download URL",
  Country = "Country",
  Subdivision = "Region (e.g Province, State)",
  Municipality = "Municipality",
  Name = "Feed Name",
  UserId = "User ID",
  LinkToDatasetLicense = "License URL",
  AuthenticationType = "Authentication Type",
  AuthenticationSignupLink = "API Key URL",
  AuthenticationParameterName = "HTTP header or API key parameter name",
  Note = "Note (any important clarifications so people know how to use your dataset)",
  UserInterview = "User interview email",
  DataProducerEmail = "Data producer email",
  OfficialProducer = "Are you the official producer or transit agency responsible for this data?",
  ToolsAndSupport = "What tools and support do you use to create your GTFS data?",
  LinkToAssociatedGTFS = "Link to associated GTFS Schedule feed",
  LogoPermission = "Do we have permission to share your logo on https://mobilitydatabase.org/contribute?",
}

/**
 *
 * @param {FeedSubmissionFormRequestBody} formData The request body from the feed submission form
 * @param {string} uid The user ID of the user submitting the feed
 * @return {RawRowData[]} Formatted rows data to be written to the Google Sheet
 */
export function buildFeedRows(
  formData: FeedSubmissionFormRequestBody,
  uid: string
): RawRowData[] {
  /* eslint-enable max-len */
  const rowsToAdd: RawRowData[] = [];
  if (formData.dataType === "gtfs") {
    rowsToAdd.push(
      buildFeedRow(formData, {
        dataTypeName: "GTFS Schedule",
        downloadUrl: formData.feedLink ?? "",
        currentUrl: formData.oldFeedLink ?? "",
        uid,
      })
    );
  } else {
    if (formData.tripUpdates) {
      rowsToAdd.push(
        buildFeedRow(formData, {
          dataTypeName: "GTFS Realtime - Trip Updates",
          downloadUrl: formData.tripUpdates ?? "",
          currentUrl: formData.oldTripUpdates ?? "",
          uid,
        })
      );
    }
    if (formData.vehiclePositions) {
      rowsToAdd.push(
        buildFeedRow(formData, {
          dataTypeName: "GTFS Realtime - Vehicle Positions",
          downloadUrl: formData.vehiclePositions ?? "",
          currentUrl: formData.oldVehiclePositions ?? "",
          uid,
        })
      );
    }
    if (formData.serviceAlerts) {
      rowsToAdd.push(
        buildFeedRow(formData, {
          dataTypeName: "GTFS Realtime - Service Alerts",
          downloadUrl: formData.serviceAlerts ?? "",
          currentUrl: formData.oldServiceAlerts ?? "",
          uid,
        })
      );
    }
  }
  return rowsToAdd;
}

/* eslint-disable max-len */

interface BuildRowParameters {
  dataTypeName: string;
  downloadUrl: string;
  currentUrl: string;
  uid: string;
}

/**
 *
 * @param {FeedSubmissionFormRequestBody} formData The request body from the feed submission form
 * @param {BuildRowParameters} formRowParameters Specific parameters based on feed type
 * @return {RawRowData} Formatted row data to be written to the Google Sheet
 */
export function buildFeedRow(
  formData: FeedSubmissionFormRequestBody,
  formRowParameters: BuildRowParameters
): RawRowData {
  const dateNow = new Date();
  return {
    [SheetCol.Status]: "Feed Submitted",
    [SheetCol.Timestamp]: dateNow.toLocaleString("en-US", {
      timeZoneName: "short",
      timeZone: "UTC",
    }),
    [SheetCol.TransitProvider]: formData.transitProviderName ?? "",
    [SheetCol.CurrentUrl]: formRowParameters.currentUrl,
    [SheetCol.DataType]: formRowParameters.dataTypeName,
    [SheetCol.IssueType]:
      formData.isUpdatingFeed === "yes" ? "Feed update" : "New feed",
    [SheetCol.DownloadUrl]: formRowParameters.downloadUrl,
    [SheetCol.Country]: formData.country,
    [SheetCol.Subdivision]: formData.region ?? "",
    [SheetCol.Municipality]: formData.municipality ?? "",
    [SheetCol.Name]: formData.name ?? "",
    [SheetCol.UserId]: formRowParameters.uid,
    [SheetCol.LinkToDatasetLicense]: formData.licensePath ?? "",
    [SheetCol.AuthenticationType]: formData.authType ?? "",
    [SheetCol.AuthenticationSignupLink]: formData.authSignupLink ?? "",
    [SheetCol.AuthenticationParameterName]: formData.authParameterName ?? "",
    [SheetCol.UserInterview]: formData.userInterviewEmail ?? "",
    [SheetCol.DataProducerEmail]: formData.dataProducerEmail ?? "",
    [SheetCol.OfficialProducer]: formData.isOfficialProducer,
    [SheetCol.ToolsAndSupport]: formData.whatToolsUsedText ?? "",
    [SheetCol.LinkToAssociatedGTFS]: formData.gtfsRelatedScheduleLink ?? "",
    [SheetCol.LogoPermission]: formData.hasLogoPermission,
  };
}

/**
 * Sends a Slack webhook message to the configured Slack webhook URL
 * @param {string} spreadsheetId The ID of the Google Sheet
 */
async function sendSlackWebhook(spreadsheetId: string) {
  const slackWebhookUrl = process.env.SLACK_WEBHOOK_URL;
  const sheetUrl = `https://docs.google.com/spreadsheets/d/${spreadsheetId}/edit`;
  if (slackWebhookUrl !== undefined && slackWebhookUrl !== "") {
    const slackMessage = {
      blocks: [
        {
          type: "header",
          text: {
            type: "plain_text",
            text: "New Feed Added",
          },
        },
        {
          type: "rich_text",
          elements: [
            {
              type: "rich_text_section",
              elements: [
                {
                  type: "emoji",
                  name: "inbox_tray",
                },
                {
                  type: "text",
                  text: "  A new entry was received in the OpenMobilityData source updates Google Sheet",
                },
              ],
            },
          ],
        },
        {
          "type": "rich_text",
          "elements": [
            {
              "type": "rich_text_section",
              "elements": [
                {
                  "type": "link",
                  "url": sheetUrl,
                  "text": "View Feed",
                  "style": {
                    "bold": true,
                  },
                },
              ],
            },
          ],
        },
      ],
    };
    await axios.post(slackWebhookUrl, slackMessage).catch((error) => {
      logger.error("Error sending Slack webhook:", error);
    });
  } else {
    logger.error("Slack webhook URL is not defined");
  }
}
/* eslint-enable max-len */
