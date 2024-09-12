import {
  buildFeedRow,
  buildFeedRows,
  SheetCol,
} from "../impl/feed-form-impl";
import {type FeedSubmissionFormRequestBody} from "../impl/types";

const sampleRequestBodyGTFS: FeedSubmissionFormRequestBody = {
  name: "Sample Feed",
  isOfficialProducer: "yes",
  dataType: "gtfs",
  transitProviderName: "Sample Transit Provider",
  feedLink: "https://example.com/feed",
  isUpdatingFeed: "yes",
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
  authType: "0 - None",
  authSignupLink: "https://example.com/signup",
  authParameterName: "auth_token",
  dataProducerEmail: "producer@example.com",
  isInterestedInQualityAudit: "yes",
  userInterviewEmail: "interviewee@example.com",
  whatToolsUsedText: "Google Sheets, Node.js",
  hasLogoPermission: "yes",
};

const sampleRequestBodyGTFSRT: FeedSubmissionFormRequestBody = {
  ...sampleRequestBodyGTFS,
  dataType: "gtfs_rt",
  feedLink: "",
  tripUpdates: "https://example.com/gtfs-realtime-trip-update",
  vehiclePositions: "https://example.com/gtfs-realtime-vehicle-position",
  serviceAlerts: "https://example.com/gtfs-realtime-service-alerts",
  oldTripUpdates: "https://example.com/old-feed-tu",
  oldServiceAlerts: "https://example.com/old-feed-sa",
  oldVehiclePositions: "https://example.com/old-feed-vp",
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
        sampleRequestBodyGTFS.feedLink ?? "",
        "https://example.com/old-feed"
      ),
    ];
    expect(buildFeedRows(sampleRequestBodyGTFS)).toEqual(expectedRows);
  });

  it("should build the rows if gtfs realtime", () => {
    const expectedRows = [
      buildFeedRow(
        sampleRequestBodyGTFSRT,
        "GTFS Realtime - Trip Updates",
        sampleRequestBodyGTFSRT.tripUpdates ?? "",
        "https://example.com/old-feed-tu"
      ),
      buildFeedRow(
        sampleRequestBodyGTFSRT,
        "GTFS Realtime - Vehicle Positions",
        sampleRequestBodyGTFSRT.vehiclePositions ?? "",
        "https://example.com/old-feed-vp"
      ),
      buildFeedRow(
        sampleRequestBodyGTFSRT,
        "GTFS Realtime - Service Alerts",
        sampleRequestBodyGTFSRT.serviceAlerts ?? "",
        "https://example.com/old-feed-sa"
      ),
    ];
    expect(buildFeedRows(sampleRequestBodyGTFSRT)).toEqual(expectedRows);
  });

  it("should format request body to row format", () => {
    const googleSheetRow = buildFeedRow(
      sampleRequestBodyGTFS,
      "GTFS Schedule",
      "https://example.com/gtfs-schedule",
      "https://example.com/old-feed"
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
      [SheetCol.UserId]: sampleRequestBodyGTFS.userId,
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
    });
  });
});
