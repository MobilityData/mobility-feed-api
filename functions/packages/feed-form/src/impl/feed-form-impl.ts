import {GoogleSpreadsheet} from "google-spreadsheet";
import {GoogleAuth} from "google-auth-library";
import {Response, Request} from "firebase-functions/v1";

export interface FeedSubmissionFormRequestBody {
  name: string;
  isOfficialProducer: boolean;
  dataType: "gtfs" | "gtfs-rt";
  transitProviderName?: string;
  feedLink?: string;
  isNewFeed: boolean;
  oldFeedLink?: string;
  licensePath?: string;
  userId: string;
  country: string;
  region?: string;
  municipality?: string;
  tripUpdates?: string;
  vehiclePositions?: string;
  serviceAlerts?: string;
  gtfsRelatedScheduleLink?: string;
  note: string;
  authType?: string;
  authSignupLink?: string;
  authParameterName?: string;
  dataProducerEmail?: string;
  isInterestedInQualityAudit: boolean;
  userInterviewEmail?: string;
  whatToolsUsedText?: string;
  hasLogoPermission: boolean;
}

const SCOPES = [
  "https://www.googleapis.com/auth/spreadsheets",
  "https://www.googleapis.com/auth/drive.file",
];

export const writeToSheet = async (request: Request, response: Response) => {
  try {
    const sheetId = process.env.FEED_SUBMIT_GOOGLE_SHEET_ID;
    if (sheetId === undefined) {
      throw new Error("Google Sheet ID is not defined");
    }
    const auth = new GoogleAuth({
      scopes: SCOPES,
    });
    const doc = await new GoogleSpreadsheet(sheetId, auth);
    await doc.loadInfo();
    const rawDataSheet = doc.sheetsByIndex[0];
    const formData: FeedSubmissionFormRequestBody = request.body;
    const rows = buildFeedRows(formData);
    await rawDataSheet.addRows(rows, {insert: true});

    response.status(200).send("Data written to the new sheet successfully!");
  } catch (error) {
    console.error("Error writing to sheet:", error);
    response.status(500).send("An error occurred while writing to the sheet.");
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
 * @return {RawRowData[]} Formatted rows data to be written to the Google Sheet
 */
export function buildFeedRows(
  formData: FeedSubmissionFormRequestBody
): RawRowData[] {
  /* eslint-enable max-len */
  const rowsToAdd: RawRowData[] = [];
  if (formData.dataType === "gtfs") {
    rowsToAdd.push(
      buildFeedRow(formData, "GTFS Schedule", formData.feedLink ?? "")
    );
  } else {
    if (formData.tripUpdates) {
      rowsToAdd.push(
        buildFeedRow(
          formData,
          "GTFS Realtime - Trip Updates",
          formData.tripUpdates ?? ""
        )
      );
    }
    if (formData.vehiclePositions) {
      rowsToAdd.push(
        buildFeedRow(
          formData,
          "GTFS Realtime - Vehicle Positions",
          formData.vehiclePositions ?? ""
        )
      );
    }
    if (formData.serviceAlerts) {
      rowsToAdd.push(
        buildFeedRow(
          formData,
          "GTFS Realtime - Service Alerts",
          formData.serviceAlerts ?? ""
        )
      );
    }
  }
  return rowsToAdd;
}

/* eslint-disable max-len */

/**
 *
 * @param {FeedSubmissionFormRequestBody} formData The request body from the feed submission form
 * @param {string} dataTypeName Specific data type name for the feed
 * @param {string} downloadUrl Feed download URL
 * @return {RawRowData} Formatted row data to be written to the Google Sheet
 */
export function buildFeedRow(
  formData: FeedSubmissionFormRequestBody,
  dataTypeName: string,
  downloadUrl: string
): RawRowData {
  /* eslint-enable max-len */
  const dateNow = new Date();
  return {
    [SheetCol.Status]: "Feed Submitted",
    [SheetCol.Timestamp]: dateNow.toLocaleString("en-US", {
      timeZoneName: "short",
      timeZone: "UTC",
    }),
    [SheetCol.TransitProvider]: formData.transitProviderName ?? "",
    [SheetCol.CurrentUrl]: formData.oldFeedLink ?? "",
    [SheetCol.DataType]: dataTypeName,
    [SheetCol.IssueType]: formData.isNewFeed ? "New feed" : "Feed update",
    [SheetCol.DownloadUrl]: downloadUrl,
    [SheetCol.Country]: formData.country,
    [SheetCol.Subdivision]: formData.region ?? "",
    [SheetCol.Municipality]: formData.municipality ?? "",
    [SheetCol.Name]: formData.name,
    [SheetCol.UserId]: formData.userId,
    [SheetCol.LinkToDatasetLicense]: formData.licensePath ?? "",
    [SheetCol.AuthenticationType]: formData.authType ?? "",
    [SheetCol.AuthenticationSignupLink]: formData.authSignupLink ?? "",
    [SheetCol.AuthenticationParameterName]: formData.authParameterName ?? "",
    [SheetCol.Note]: formData.note,
    [SheetCol.UserInterview]: formData.userInterviewEmail ?? "",
    [SheetCol.DataProducerEmail]: formData.dataProducerEmail ?? "",
    [SheetCol.OfficialProducer]: formData.isOfficialProducer,
    [SheetCol.ToolsAndSupport]: formData.whatToolsUsedText ?? "",
    [SheetCol.LinkToAssociatedGTFS]: formData.gtfsRelatedScheduleLink ?? "",
    [SheetCol.LogoPermission]: formData.hasLogoPermission,
  };
}
