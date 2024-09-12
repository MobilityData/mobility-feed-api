export type YesNoFormInput = "yes" | "no" | "";
export type AuthTypes =
  | "0 - None"
  | "API key - 1"
  | "HTTP header - 2"
  | "choiceRequired";

export interface FeedSubmissionFormRequestBody {
  isOfficialProducer: YesNoFormInput;
  dataType: "gtfs" | "gtfs_rt";
  transitProviderName?: string;
  feedLink?: string;
  isUpdatingFeed: YesNoFormInput;
  oldFeedLink?: string;
  licensePath?: string;
  country: string;
  region?: string;
  municipality?: string;
  tripUpdates?: string;
  vehiclePositions?: string;
  serviceAlerts?: string;
  oldTripUpdates?: string;
  oldVehiclePositions?: string;
  oldServiceAlerts?: string;
  gtfsRelatedScheduleLink?: string;
  name?: string;
  authType: AuthTypes;
  authSignupLink?: string;
  authParameterName?: string;
  dataProducerEmail?: string;
  isInterestedInQualityAudit: YesNoFormInput;
  userInterviewEmail?: string;
  whatToolsUsedText?: string;
  hasLogoPermission: YesNoFormInput;
  userId: string;
}
