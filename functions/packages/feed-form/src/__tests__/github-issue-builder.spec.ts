import {buildGithubIssueBody} from "../impl/feed-form-impl";
import {FeedSubmissionFormRequestBody} from "../impl/types";

describe("buildGithubIssueBody", () => {
  const spreadsheetId = "testSpreadsheetId";

  it("should generate content for basic form data with GTFS feed", () => {
    const formData: FeedSubmissionFormRequestBody = {
      isOfficialProducer: "yes",
      isOfficialFeed: "yes",
      dataType: "gtfs",
      transitProviderName: "Test Agency",
      name: "Test Agency",
      country: "US",
      region: "CA",
      municipality: "San Francisco",
      isUpdatingFeed: "yes",
      oldFeedLink: "https://old-feed-link.com",
      feedLink: "https://new-feed-link.com",
      authType: "API key - 1",
      authSignupLink: "https://auth-signup-link.com",
      authParameterName: "apiKey",
      isInterestedInQualityAudit: "no",
      hasLogoPermission: "yes",
    };

    const expectedContent = `
  # Agency name/Transit Provider: Test Agency

  ### Location
  US, CA, San Francisco

  ## Details

  #### Data type
  gtfs

  #### Issue type
  Feed update

  #### Name
  Test Agency

  ## URLs
  | Current URL on OpenMobilityData.org | Updated/new feed URL |
  |---|---|
  | https://old-feed-link.com | https://new-feed-link.com |

  ## Authentication
  #### Authentication type
  API key - 1

  #### Link to how to sign up for authentication credentials (API KEY)
  https://auth-signup-link.com

  #### HTTP header or API key parameter name
  apiKey

  ## View more details
  https://docs.google.com/spreadsheets/d/testSpreadsheetId/edit`;

    expect(buildGithubIssueBody(formData, spreadsheetId)).toBe(expectedContent);
  });

  it("should handle optional location fields gracefully", () => {
    const formData: FeedSubmissionFormRequestBody = {
      isOfficialProducer: "no",
      isOfficialFeed: "yes",
      dataType: "gtfs",
      transitProviderName: "Test Agency",
      name: "Test Agency",
      country: "US",
      isUpdatingFeed: "no",
      oldFeedLink: "https://old-feed-link.com",
      feedLink: "https://new-feed-link.com",
      authType: "HTTP header - 2",
      isInterestedInQualityAudit: "",
      hasLogoPermission: "no",
    };

    const expectedContent = `
  # Agency name/Transit Provider: Test Agency

  ### Location
  US

  ## Details

  #### Data type
  gtfs

  #### Issue type
  New feed

  #### Name
  Test Agency

  ## URLs
  | Current URL on OpenMobilityData.org | Updated/new feed URL |
  |---|---|
  | https://old-feed-link.com | https://new-feed-link.com |

  ## Authentication
  #### Authentication type
  HTTP header - 2

  ## View more details
  https://docs.google.com/spreadsheets/d/testSpreadsheetId/edit`;

    expect(buildGithubIssueBody(formData, spreadsheetId)).toBe(expectedContent);
  });

  it("should handle non-GTFS data types (tu, vp, sa)", () => {
    const formData: FeedSubmissionFormRequestBody = {
      isOfficialProducer: "yes",
      isOfficialFeed: "yes",
      dataType: "gtfs_rt",
      transitProviderName: "Test Agency",
      name: "Test Agency",
      isUpdatingFeed: "yes",
      oldTripUpdates: "https://old-trip-updates.com",
      tripUpdates: "https://new-trip-updates.com",
      oldVehiclePositions: "https://old-vehicle-positions.com",
      vehiclePositions: "https://new-vehicle-positions.com",
      oldServiceAlerts: "https://old-service-alerts.com",
      serviceAlerts: "https://new-service-alerts.com",
      authType: "None - 0",
      isInterestedInQualityAudit: "yes",
      hasLogoPermission: "no",
    };

    const expectedContent = `
  # Agency name/Transit Provider: Test Agency

  ## Details

  #### Data type
  gtfs_rt

  #### Issue type
  Feed update

  #### Name
  Test Agency

  ## URLs
  | Current URL on OpenMobilityData.org | Updated/new feed URL |
  |---|---|
  | https://old-trip-updates.com | https://new-trip-updates.com |
  | https://old-vehicle-positions.com | https://new-vehicle-positions.com |
  | https://old-service-alerts.com | https://new-service-alerts.com |

  ## Authentication
  #### Authentication type
  None - 0

  ## View more details
  https://docs.google.com/spreadsheets/d/testSpreadsheetId/edit`;
    expect(buildGithubIssueBody(formData, spreadsheetId)).toBe(expectedContent);
  });

  it("should handle missing authentication details", () => {
    const formData: FeedSubmissionFormRequestBody = {
      isOfficialProducer: "",
      isOfficialFeed: "yes",
      dataType: "gtfs",
      transitProviderName: "Test Agency",
      name: "Test Agency",
      isUpdatingFeed: "no",
      oldFeedLink: "https://old-feed-link.com",
      feedLink: "https://new-feed-link.com",
      authType: "None - 0",
      isInterestedInQualityAudit: "",
      hasLogoPermission: "",
    };

    const expectedContent = `
  # Agency name/Transit Provider: Test Agency

  ## Details

  #### Data type
  gtfs

  #### Issue type
  New feed

  #### Name
  Test Agency

  ## URLs
  | Current URL on OpenMobilityData.org | Updated/new feed URL |
  |---|---|
  | https://old-feed-link.com | https://new-feed-link.com |

  ## Authentication
  #### Authentication type
  None - 0

  ## View more details
  https://docs.google.com/spreadsheets/d/testSpreadsheetId/edit`;

    expect(buildGithubIssueBody(formData, spreadsheetId)).toBe(expectedContent);
  });
});
