import {GoogleSpreadsheet} from "google-spreadsheet";
import {JWT} from "google-auth-library";
import {Response, Request} from "firebase-functions/v1";

export interface FeedSubmissionFormRequestBody {
  name: string;
  isOfficialProducer: boolean;
  dataType: string;
  transitProviderName?: string;
  feedLink: string;
  isNewFeed: boolean;
  oldFeedLink?: string;
  licensePath?: string;
  userId: string;
  country: string;
  region?: string;
  municipality?: string;
  tripUpdates?: boolean;
  vehiclePositions?: boolean;
  serviceAlerts?: boolean;
  gtfsRealtimeLink: string;
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

export const writeToSheet = async (
  request: Request,
  response: Response,
  secrets: { sheetId: string; serviceEmail: string; privateKey: string }
) => {
  try {
    const jwt = new JWT({
      email: secrets.serviceEmail,
      key: secrets.privateKey,
      scopes: SCOPES,
    });
    const doc = new GoogleSpreadsheet(secrets.sheetId, jwt);
    await doc.loadInfo();
    const rawDataSheet = doc.sheetsByIndex[0];
    const formData: FeedSubmissionFormRequestBody = request.body;
    const row = buildFeedRow(formData);
    await rawDataSheet.addRow(row, {insert: true});

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
enum SheetCol {
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
  TripUpdatesUrl = "Trip Updates URL",
  ServiceAlertsUrl = "Service Alerts URL",
  VehiclePositionUrl = "Vehicle Positions URL",
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
 * Takes the request body from the feed submission form and formats it into a row
 * @param {FeedSubmissionFormRequestBody} formData The request body from the feed submission form
 * @return {RawRowData} Formatted row data to be written to the Google Sheet
 */
export function buildFeedRow(
  formData: FeedSubmissionFormRequestBody
): RawRowData {
  /* eslint-enable max-len */
  const dateNow = new Date();
  return {
    [SheetCol.Status]: "Feed Submitted",
    [SheetCol.Timestamp]: dateNow.toLocaleString("en-US", {
      timeZoneName: "short",
    }),
    [SheetCol.TransitProvider]: formData.transitProviderName ?? "",
    [SheetCol.CurrentUrl]: formData.oldFeedLink ?? "",
    [SheetCol.DataType]: formData.dataType,
    [SheetCol.IssueType]: formData.isNewFeed ? "New feed" : "Feed update",
    [SheetCol.DownloadUrl]: formData.feedLink,
    [SheetCol.Country]: formData.country,
    [SheetCol.Subdivision]: formData.region ?? "",
    [SheetCol.Municipality]: formData.municipality ?? "",
    [SheetCol.Name]: formData.name,
    [SheetCol.UserId]: formData.userId,
    [SheetCol.LinkToDatasetLicense]: formData.licensePath ?? "",
    [SheetCol.TripUpdatesUrl]: formData.tripUpdates ?? "",
    [SheetCol.ServiceAlertsUrl]: formData.serviceAlerts ?? "",
    [SheetCol.VehiclePositionUrl]: formData.vehiclePositions ?? "",
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
