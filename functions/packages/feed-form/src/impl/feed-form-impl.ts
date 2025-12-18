import {GoogleSpreadsheet} from "google-spreadsheet";
import {GoogleAuth} from "google-auth-library";
import * as logger from "firebase-functions/logger";
import {type FeedSubmissionFormRequestBody} from "./types";
import {type CallableRequest, HttpsError} from "firebase-functions/v2/https";
import axios from "axios";
import {countries, continents, type TCountryCode} from "countries-list";

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

    const projectId = process.env.GCLOUD_PROJECT || process.env.GCP_PROJECT;
    const isProduction = projectId === "mobility-feeds-prod";
    let githubIssueUrl = "";
    if (
      process.env.GITHUB_TOKEN !== undefined &&
      process.env.GITHUB_TOKEN !== "" &&
      isProduction
    ) {
      githubIssueUrl = await createGithubIssue(
        formData,
        sheetId,
        process.env.GITHUB_TOKEN
      );
    }
    await sendSlackWebhook(
      sheetId,
      githubIssueUrl,
      formData.isOfficialFeed === "yes"
    );
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
  OfficialFeedSource = "Is Official Feed Source",
  ToolsAndSupport = "What tools and support do you use to create your GTFS data?",
  LinkToAssociatedGTFS = "Link to associated GTFS Schedule feed",
  LogoPermission = "Do we have permission to share your logo on https://mobilitydatabase.org/contribute?",
  UnofficialDesc = "Why was this feed created?",
  UpdateFreq = "How often is this feed updated?",
  EmptyLicenseUsage = "Feed intended for trip planners/third parties?",
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
    [SheetCol.Country]: formData.country ?? "",
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
    [SheetCol.OfficialFeedSource]: formData.isOfficialFeed ?? "",
    [SheetCol.ToolsAndSupport]: formData.whatToolsUsedText ?? "",
    [SheetCol.LinkToAssociatedGTFS]: formData.gtfsRelatedScheduleLink ?? "",
    [SheetCol.LogoPermission]: formData.hasLogoPermission,
    [SheetCol.UnofficialDesc]: formData.unofficialDesc ?? "",
    [SheetCol.UpdateFreq]: formData.updateFreq ?? "",
    [SheetCol.EmptyLicenseUsage]: formData.emptyLicenseUsage ?? "",
  };
}

/**
 * Sends a Slack webhook message to the configured Slack webhook URL
 * @param {string} spreadsheetId The ID of the Google Sheet
 * @param {string} githubIssueUrl The URL of the created GitHub issue
 * @param {boolean} isOfficialSource Whether the feed is an official source
 */
async function sendSlackWebhook(
  spreadsheetId: string,
  githubIssueUrl: string,
  isOfficialSource: boolean
) {
  const slackWebhookUrl = process.env.SLACK_WEBHOOK_URL;
  const sheetUrl = `https://docs.google.com/spreadsheets/d/${spreadsheetId}/edit`;
  if (slackWebhookUrl !== undefined && slackWebhookUrl !== "") {
    let headerText = "New Feed Added";
    if (isOfficialSource) {
      headerText += " 🔹 Official Source";
    }
    const linksElement = [
      {
        type: "emoji",
        name: "google_drive",
      },
      {
        type: "link",
        url: sheetUrl,
        text: " View Feed ",
        style: {
          bold: true,
        },
      },
    ];
    if (githubIssueUrl !== "") {
      linksElement.push(
        {
          type: "emoji",
          name: "github-logo",
        },
        {
          type: "link",
          url: githubIssueUrl,
          text: " View Issue ",
          style: {
            bold: true,
          },
        }
      );
    }
    const slackMessage = {
      blocks: [
        {
          type: "header",
          text: {
            type: "plain_text",
            text: headerText,
            emoji: true,
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
          type: "rich_text",
          elements: [
            {
              type: "rich_text_section",
              elements: linksElement,
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

/**
 * Creates a GitHub issue in the Mobility Database Catalogs repository
 * @param {FeedSubmissionFormRequestBody} formData feed submission form
 * @param {string} spreadsheetId googleshhet id
 * @param  {string} githubToken github token to create the issue
 * @return {Promise<string>} The URL of the created GitHub issue
 */
async function createGithubIssue(
  formData: FeedSubmissionFormRequestBody,
  spreadsheetId: string,
  githubToken: string
): Promise<string> {
  const githubRepoUrlIssue =
    "https://api.github.com/repos/MobilityData/mobility-database-catalogs/issues";
  let issueTitle =
    "New Feed Added" +
    (formData.transitProviderName ? `: ${formData.transitProviderName}` : "");
  if (formData.isOfficialFeed === "yes") {
    issueTitle += " - Official Feed";
  }
  const issueBody = buildGithubIssueBody(formData, spreadsheetId);

  const labels = ["feed submission"];
  if (formData.country && formData.country in countries) {
    const country = countries[formData.country as TCountryCode];
    const continent = continents[country.continent].toLowerCase();
    if (continent != null) labels.push(`region/${continent}`);
  }

  if (formData.authType !== "None - 0") {
    labels.push("auth required");
  }

  try {
    const response = await axios.post(
      githubRepoUrlIssue,
      {
        title: issueTitle,
        body: issueBody,
        labels,
      },
      {
        headers: {
          Authorization: `token ${githubToken}`,
          Accept: "application/vnd.github.v3+json",
        },
      }
    );
    return response.data.html_url;
  } catch (error) {
    logger.error("Error creating GitHub issue:", error);
    return "";
  }
}

// Markdown format is strange in strings, so we disable eslint for this function
/* eslint-disable */
export function buildGithubIssueBody(
  formData: FeedSubmissionFormRequestBody,
  spreadsheetId: string
) {
  let content = "";
  if (formData.transitProviderName) {
    content += `
  # Agency name/Transit Provider: ${formData.name}`;
  }

  if (formData.country || formData.region || formData.municipality) {
    let locationName = formData.country ?? "";
    locationName += formData.region ? `, ${formData.region}` : "";
    locationName += formData.municipality ? `, ${formData.municipality}` : "";
    content += `

  ### Location
  ${locationName}`;
  }

  content += `

  ## Details`;

  content += `

  #### Data type
  ${formData.dataType}

  #### Issue type
  ${formData.isUpdatingFeed === "yes" ? "Feed update" : "New feed"}`;

  if (formData.name) {
    content += `

  #### Name
  ${formData.name}`;
  }

  content += `

  ## URLs
  | Current URL on OpenMobilityData.org | Updated/new feed URL |
  |---|---|`;
  if (formData.dataType === "gtfs") {
    content += `
  | ${formData.oldFeedLink} | ${formData.feedLink} |`;
  } else {
    if (formData.tripUpdates) {
      content += `
  | ${formData.oldTripUpdates} | ${formData.tripUpdates} |`;
    }
    if (formData.vehiclePositions) {
      content += `
  | ${formData.oldVehiclePositions} | ${formData.vehiclePositions} |`;
    }
    if (formData.serviceAlerts) {
      content += `
  | ${formData.oldServiceAlerts} | ${formData.serviceAlerts} |`;
    }
  }

  content += `

  ## Authentication
  #### Authentication type
  ${formData.authType}`;
  if (formData.authSignupLink) {
    content += `

  #### Link to how to sign up for authentication credentials (API KEY)
  ${formData.authSignupLink}`;
  }
  if (formData.authParameterName) {
    content += `

  #### HTTP header or API key parameter name
  ${formData.authParameterName}`;
  }

  content += `

  ## View more details
  https://docs.google.com/spreadsheets/d/${spreadsheetId}/edit`;
  return content;
}
/* eslint-enable */
