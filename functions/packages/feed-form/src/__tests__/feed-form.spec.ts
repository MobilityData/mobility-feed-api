import {buildFeedRow, SheetCol} from "../impl/feed-form-impl";

const sampleRequestBody = {
  name: "Sample Feed",
  isOfficialProducer: true,
  dataType: "GTFS",
  transitProviderName: "Sample Transit Provider",
  feedLink: "https://example.com/feed",
  isNewFeed: true,
  oldFeedLink: "https://example.com/old-feed",
  licensePath: "/path/to/license",
  userId: "user123",
  country: "USA",
  region: "California",
  municipality: "San Francisco",
  tripUpdates: true,
  vehiclePositions: true,
  serviceAlerts: true,
  gtfsRealtimeLink: "https://example.com/gtfs-realtime",
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

describe("Feed Form Implementation", () => {
  beforeAll(() => {
    const mockDate = new Date("2023-08-01T00:00:00Z");
    jest.spyOn(global, "Date").mockImplementation(() => mockDate);
  });

  it("should format request body to row format", () => {
    const googleSheetRow = buildFeedRow(sampleRequestBody);
    expect(googleSheetRow).toEqual({
      [SheetCol.Status]: "Feed Submitted",
      [SheetCol.Timestamp]: "8/1/2023, 12:00:00 AM UTC",
      [SheetCol.TransitProvider]: sampleRequestBody.transitProviderName,
      [SheetCol.CurrentUrl]: sampleRequestBody.oldFeedLink,
      [SheetCol.DataType]: sampleRequestBody.dataType,
      [SheetCol.IssueType]: "New feed",
      [SheetCol.DownloadUrl]: sampleRequestBody.feedLink,
      [SheetCol.Country]: sampleRequestBody.country,
      [SheetCol.Subdivision]: sampleRequestBody.region,
      [SheetCol.Municipality]: sampleRequestBody.municipality,
      [SheetCol.Name]: sampleRequestBody.name,
      [SheetCol.UserId]: sampleRequestBody.userId,
      [SheetCol.LinkToDatasetLicense]: sampleRequestBody.licensePath,
      [SheetCol.TripUpdatesUrl]: sampleRequestBody.tripUpdates,
      [SheetCol.ServiceAlertsUrl]: sampleRequestBody.serviceAlerts,
      [SheetCol.VehiclePositionUrl]: sampleRequestBody.vehiclePositions,
      [SheetCol.AuthenticationType]: sampleRequestBody.authType,
      [SheetCol.AuthenticationSignupLink]: sampleRequestBody.authSignupLink,
      [SheetCol.AuthenticationParameterName]:
        sampleRequestBody.authParameterName,
      [SheetCol.Note]: sampleRequestBody.note,
      [SheetCol.UserInterview]: sampleRequestBody.userInterviewEmail,
      [SheetCol.DataProducerEmail]: sampleRequestBody.dataProducerEmail,
      [SheetCol.OfficialProducer]: sampleRequestBody.isOfficialProducer,
      [SheetCol.ToolsAndSupport]: sampleRequestBody.whatToolsUsedText,
      [SheetCol.LinkToAssociatedGTFS]:
        sampleRequestBody.gtfsRelatedScheduleLink,
      [SheetCol.LogoPermission]: sampleRequestBody.hasLogoPermission,
    });
  });
});
