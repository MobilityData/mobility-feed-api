import {countries, continents, type TCountryCode} from "countries-list";
import {isValidZipUrl, isValidZipDownload} from "./url-parse";
import {type FeedSubmissionFormRequestBody} from "../types";
import axios from "axios";
import * as logger from "firebase-functions/logger";

/**
 * Creates a GitHub issue in the Mobility Database Catalogs repository
 * @param {FeedSubmissionFormRequestBody} formData feed submission form
 * @param {string} spreadsheetId googleshhet id
 * @param  {string} githubToken github token to create the issue
 * @return {Promise<string>} The URL of the created GitHub issue
 */
export async function createGithubIssue(
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

  if (!isValidZipUrl(formData.feedLink)) {
    if (!await isValidZipDownload(formData.feedLink)) {
      labels.push("invalid");
    }
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