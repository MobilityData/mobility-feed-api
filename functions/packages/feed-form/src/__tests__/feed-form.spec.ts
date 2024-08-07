import {
  buildFeedRow,
  buildFeedRows,
  FeedSubmissionFormRequestBody,
  SheetCol,
} from "../impl/feed-form-impl";

const sampleRequestBodyGTFS: FeedSubmissionFormRequestBody = {
  name: "Sample Feed",
  isOfficialProducer: true,
  dataType: "gtfs",
  transitProviderName: "Sample Transit Provider",
  feedLink: "https://example.com/feed",
  isNewFeed: true,
  oldFeedLink: "https://example.com/old-feed",
  licensePath: "/path/to/license",
  userId: "user123",
  country: "USA",
  region: "California",
  municipality: "San Francisco",
  tripUpdates: "",
  vehiclePositions: "",
  serviceAlerts: "",
  gtfsRelatedScheduleLink: "https://example.com/gtfs-schedule",
  note: "This is a sample note.",
  authType: "OAuth",
  authSignupLink: "https://example.com/signup",
  authParameterName: "auth_token",
  dataProducerEmail: "producer@example.com",
  isInterestedInQualityAudit: true,
  userInterviewEmail: "interviewee@example.com",
  whatToolsUsedText: "Google Sheets, Node.js",
  hasLogoPermission: true,
};

const sampleRequestBodyGTFSRT: FeedSubmissionFormRequestBody = {
  ...sampleRequestBodyGTFS,
  dataType: "gtfs-rt",
  feedLink: "",
  tripUpdates: "https://example.com/gtfs-realtime-trip-update",
  vehiclePositions: "https://example.com/gtfs-realtime-vehicle-position",
  serviceAlerts: "https://example.com/gtfs-realtime-service-alerts",
};

describe("Feed Form Implementation", () => {
  beforeAll(() => {
    const mockDate = new Date("2023-08-01T00:00:00Z");
    jest.spyOn(global, "Date").mockImplementation(() => mockDate);
  });

  it("should build the rows if gtfs schedule", () => {
    buildFeedRows(sampleRequestBodyGTFS);
    const expectedRows = [
      buildFeedRow(
        sampleRequestBodyGTFS,
        "GTFS Schedule",
        sampleRequestBodyGTFS.feedLink ?? ""
      ),
    ];
    expect(buildFeedRows(sampleRequestBodyGTFS)).toEqual(expectedRows);
  });

  it("should build the rows if gtfs realtime", () => {
    const expectedRows = [
      buildFeedRow(
        sampleRequestBodyGTFSRT,
        "GTFS Realtime - Trip Updates",
        sampleRequestBodyGTFSRT.tripUpdates ?? ""
      ),
      buildFeedRow(
        sampleRequestBodyGTFSRT,
        "GTFS Realtime - Vehicle Positions",
        sampleRequestBodyGTFSRT.vehiclePositions ?? ""
      ),
      buildFeedRow(
        sampleRequestBodyGTFSRT,
        "GTFS Realtime - Service Alerts",
        sampleRequestBodyGTFSRT.serviceAlerts ?? ""
      ),
    ];
    expect(buildFeedRows(sampleRequestBodyGTFSRT)).toEqual(expectedRows);
  });

  it("should format request body to row format", () => {
    const googleSheetRow = buildFeedRow(
      sampleRequestBodyGTFS,
      "GTFS Schedule",
      "https://example.com/gtfs-schedule"
    );
    expect(googleSheetRow).toEqual({
      [SheetCol.Status]: "Feed Submitted",
      [SheetCol.Timestamp]: "8/1/2023, 12:00:00 AM UTC",
      [SheetCol.TransitProvider]: sampleRequestBodyGTFS.transitProviderName,
      [SheetCol.CurrentUrl]: sampleRequestBodyGTFS.oldFeedLink,
      [SheetCol.DataType]: "GTFS Schedule",
      [SheetCol.IssueType]: "New feed",
      [SheetCol.DownloadUrl]: "https://example.com/gtfs-schedule",
      [SheetCol.Country]: sampleRequestBodyGTFS.country,
      [SheetCol.Subdivision]: sampleRequestBodyGTFS.region,
      [SheetCol.Municipality]: sampleRequestBodyGTFS.municipality,
      [SheetCol.Name]: sampleRequestBodyGTFS.name,
      [SheetCol.UserId]: sampleRequestBodyGTFS.userId,
      [SheetCol.LinkToDatasetLicense]: sampleRequestBodyGTFS.licensePath,
      [SheetCol.AuthenticationType]: sampleRequestBodyGTFS.authType,
      [SheetCol.AuthenticationSignupLink]: sampleRequestBodyGTFS.authSignupLink,
      [SheetCol.AuthenticationParameterName]:
        sampleRequestBodyGTFS.authParameterName,
      [SheetCol.Note]: sampleRequestBodyGTFS.note,
      [SheetCol.UserInterview]: sampleRequestBodyGTFS.userInterviewEmail,
      [SheetCol.DataProducerEmail]: sampleRequestBodyGTFS.dataProducerEmail,
      [SheetCol.OfficialProducer]: sampleRequestBodyGTFS.isOfficialProducer,
      [SheetCol.ToolsAndSupport]: sampleRequestBodyGTFS.whatToolsUsedText,
      [SheetCol.LinkToAssociatedGTFS]:
        sampleRequestBodyGTFS.gtfsRelatedScheduleLink,
      [SheetCol.LogoPermission]: sampleRequestBodyGTFS.hasLogoPermission,
    });
  });
});
