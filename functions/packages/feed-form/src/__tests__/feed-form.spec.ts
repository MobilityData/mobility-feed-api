import {
  buildFeedRow,
  buildFeedRows,
  SheetCol,
  writeToSheet,
} from "../impl/feed-form-impl";
import * as logger from "firebase-functions/logger";
import {sampleRequestBodyGTFS, sampleRequestBodyGTFSRT} from "../impl/__mocks__/FeedSubmissionFormRequestBody.mock";
import {HttpsError} from "firebase-functions/v2/https";

jest.mock("google-spreadsheet", () => ({
  GoogleSpreadsheet: jest.fn().mockImplementation(() => ({
    loadInfo: jest.fn(),
    sheetsByIndex: [
      {
        addRows: jest.fn(),
      },
    ],
  })),
}));
jest.mock("google-auth-library", () => ({
  GoogleAuth: jest.fn(),
}));

const mockCreateGithubIssue = jest.fn().mockResolvedValue("https://github.com/issue/1");
const mockSendSlackWebhook = jest.fn().mockResolvedValue(undefined);

jest.mock("../impl/utils/github-issue", () => ({
  createGithubIssue: (...args: any[]) => mockCreateGithubIssue(...args),
}));
jest.mock("../impl/utils/slack", () => ({
  sendSlackWebhook: (...args: any[]) => mockSendSlackWebhook(...args),
}));

jest.spyOn(logger, "error").mockImplementation(() => {});

const defaultEnv = process.env;

describe("Feed Form Implementation", () => {

  beforeAll(() => {
    const mockDate = new Date("2023-08-01T00:00:00Z");
    jest.spyOn(global, "Date").mockImplementation(() => mockDate);
  });

    beforeEach(() => {
    jest.clearAllMocks();
    process.env = { ...defaultEnv };
    process.env.FEED_SUBMIT_GOOGLE_SHEET_ID = "sheet123";
    process.env.GCLOUD_PROJECT = "mobility-feeds-prod";
    process.env.GITHUB_TOKEN = "token";
    process.env.SLACK_WEBHOOK_URL = "https://slack";
  });

  afterAll(() => {
    process.env = defaultEnv;
  });

  it("should throw HttpsError if sheet ID is not defined", async () => {
    process.env.FEED_SUBMIT_GOOGLE_SHEET_ID = "";
    const mockRequest = {
      auth: { uid: "user1" },
      data: sampleRequestBodyGTFS,
    };
    await expect(writeToSheet(mockRequest as any)).rejects.toThrow(HttpsError);
    expect(logger.error).toHaveBeenCalledWith(
      "Error writing to sheet:",
      expect.any(HttpsError)
    );
  });

  it("writeToSheet writes to sheet, creates github issue, sends slack, returns success", async () => {
    const mockRequest = {
      auth: { uid: "user1" },
      data: sampleRequestBodyGTFS,
    };
    const result = await writeToSheet(mockRequest as any);
    const { GoogleSpreadsheet } = require("google-spreadsheet");
    expect(GoogleSpreadsheet).toHaveBeenCalledWith("sheet123", expect.anything());
    const doc = GoogleSpreadsheet.mock.results[0].value;
    expect(doc.loadInfo).toHaveBeenCalled();
    expect(doc.sheetsByIndex[0].addRows).toHaveBeenCalledWith(
      expect.any(Array),
      { insert: true }
    );
    expect(mockCreateGithubIssue).toHaveBeenCalled();
    expect(mockSendSlackWebhook).toHaveBeenCalledWith(
      "sheet123",
      "https://github.com/issue/1",
      true
    );
    expect(result).toEqual({ message: "Data written to the new sheet successfully!" });
  });

  it("should build the rows if gtfs schedule", () => {
    buildFeedRows(sampleRequestBodyGTFS, "user123");
    const expectedRows = [
      buildFeedRow(
        sampleRequestBodyGTFS,
        {
          dataTypeName: "GTFS Schedule",
          downloadUrl: sampleRequestBodyGTFS.feedLink ?? "",
          currentUrl: "https://example.com/old-feed",
          uid: "user123",
        }
      ),
    ];
    expect(buildFeedRows(sampleRequestBodyGTFS, "user123")).toEqual(
      expectedRows
    );
  });

  it("should build the rows if gtfs realtime", () => {
    const expectedRows = [
      buildFeedRow(
        sampleRequestBodyGTFSRT,
        {
          dataTypeName: "GTFS Realtime - Trip Updates",
          downloadUrl: sampleRequestBodyGTFSRT.tripUpdates ?? "",
          currentUrl: "https://example.com/old-feed-tu",
          uid: "user123",
        }
      ),
      buildFeedRow(
        sampleRequestBodyGTFSRT,
        {
          dataTypeName: "GTFS Realtime - Vehicle Positions",
          downloadUrl: sampleRequestBodyGTFSRT.vehiclePositions ?? "",
          currentUrl: "https://example.com/old-feed-vp",
          uid: "user123",
        }
      ),
      buildFeedRow(
        sampleRequestBodyGTFSRT,
        {
          dataTypeName: "GTFS Realtime - Service Alerts",
          downloadUrl: sampleRequestBodyGTFSRT.serviceAlerts ?? "",
          currentUrl: "https://example.com/old-feed-sa",
          uid: "user123",
        }
      ),
    ];
    expect(buildFeedRows(sampleRequestBodyGTFSRT, "user123")).toEqual(
      expectedRows
    );
  });

  it("should format request body to row format", () => {
    const googleSheetRow = buildFeedRow(
      sampleRequestBodyGTFS,
      {
        dataTypeName: "GTFS Schedule",
        downloadUrl: "https://example.com/gtfs-schedule",
        currentUrl: "https://example.com/old-feed",
        uid: "user123",
      }
    );
    expect(googleSheetRow).toEqual({
      [SheetCol.Status]: "Feed Submitted",
      [SheetCol.Timestamp]: "8/1/2023, 12:00:00 AM UTC",
      [SheetCol.TransitProvider]: sampleRequestBodyGTFS.transitProviderName,
      [SheetCol.CurrentUrl]: sampleRequestBodyGTFS.oldFeedLink,
      [SheetCol.DataType]: "GTFS Schedule",
      [SheetCol.IssueType]: "Feed update",
      [SheetCol.DownloadUrl]: "https://example.com/gtfs-schedule",
      [SheetCol.Country]: sampleRequestBodyGTFS.country,
      [SheetCol.Subdivision]: sampleRequestBodyGTFS.region,
      [SheetCol.Municipality]: sampleRequestBodyGTFS.municipality,
      [SheetCol.Name]: sampleRequestBodyGTFS.name,
      [SheetCol.UserId]: "user123",
      [SheetCol.LinkToDatasetLicense]: sampleRequestBodyGTFS.licensePath,
      [SheetCol.AuthenticationType]: sampleRequestBodyGTFS.authType,
      [SheetCol.AuthenticationSignupLink]: sampleRequestBodyGTFS.authSignupLink,
      [SheetCol.AuthenticationParameterName]:
        sampleRequestBodyGTFS.authParameterName,
      [SheetCol.UserInterview]: sampleRequestBodyGTFS.userInterviewEmail,
      [SheetCol.DataProducerEmail]: sampleRequestBodyGTFS.dataProducerEmail,
      [SheetCol.OfficialProducer]: sampleRequestBodyGTFS.isOfficialProducer,
      [SheetCol.ToolsAndSupport]: sampleRequestBodyGTFS.whatToolsUsedText,
      [SheetCol.LinkToAssociatedGTFS]:
        sampleRequestBodyGTFS.gtfsRelatedScheduleLink,
      [SheetCol.LogoPermission]: sampleRequestBodyGTFS.hasLogoPermission,
      [SheetCol.UnofficialDesc]: sampleRequestBodyGTFS.unofficialDesc,
      [SheetCol.UpdateFreq]: sampleRequestBodyGTFS.updateFreq,
      [SheetCol.EmptyLicenseUsage]: sampleRequestBodyGTFS.emptyLicenseUsage,
      [SheetCol.OfficialFeedSource]: sampleRequestBodyGTFS.isOfficialFeed,
    });
  });
});
