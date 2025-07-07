import {
  buildFeedRow,
  buildFeedRows,
  SheetCol,
} from "../impl/feed-form-impl";
import {type FeedSubmissionFormRequestBody} from "../impl/types";

const sampleRequestBodyGTFS: FeedSubmissionFormRequestBody = {
  name: "Sample Feed",
  isOfficialProducer: "yes",
  isOfficialFeed: "yes",
  dataType: "gtfs",
  transitProviderName: "Sample Transit Provider",
  feedLink: "https://example.com/feed",
  isUpdatingFeed: "yes",
  oldFeedLink: "https://example.com/old-feed",
  licensePath: "/path/to/license",
  country: "USA",
  region: "California",
  municipality: "San Francisco",
  tripUpdates: "",
  vehiclePositions: "",
  serviceAlerts: "",
  gtfsRelatedScheduleLink: "https://example.com/gtfs-schedule",
  authType: "None - 0",
  authSignupLink: "https://example.com/signup",
  authParameterName: "auth_token",
  dataProducerEmail: "producer@example.com",
  isInterestedInQualityAudit: "yes",
  userInterviewEmail: "interviewee@example.com",
  whatToolsUsedText: "Google Sheets, Node.js",
  hasLogoPermission: "yes",
  unofficialDesc: "For research purposes",
  updateFreq: "every month",
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
      [SheetCol.OfficialFeedSource]: sampleRequestBodyGTFS.isOfficialFeed,
    });
  });
});
