import React from 'react';
import FormFirstStep from './FirstStep';
import FormSecondStep from './SecondStep';
import FormSecondStepRT from './SecondStepRealtime';
import FormThirdStep from './ThirdStep';

export interface FeedSubmissionFormProps {
  activeStep: number;
  handleBack: () => void;
  handleNext: () => void;
}

// This is the request body required for the API
// FeedSubmissionFormFormInput should extend this
export interface FeedSubmissionFormBody {
  name: string;
  isOfficialProducer: boolean;
  dataType: 'gtfs' | 'gtfs-rt';
  transitProviderName?: string;
  feedLink?: string;
  isNewFeed: boolean;
  oldFeedLink?: string;
  licensePath?: string;
  userId: string;
  country: string;
  region?: string;
  municipality?: string;
  tripUpdates?: string;
  vehiclePositions?: string;
  serviceAlerts?: string;
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

export interface FeedSubmissionFormFormInput {
  name: string;
  isOfficialProducer: string;
  dataType: string;
  transitProviderName: string;
  feedLink: string;
  licensePath: string;
  country: string;
  region: string;
  municipality: string;
  tripUpdates: boolean;
  vehiclePositions: boolean;
  serviceAlerts: boolean;
  gtfsRealtimeLink: string;
  gtfsRelatedScheduleLink: string;
  note: string;
  isAuthRequired: string;
  dataProducerEmail: string;
  isInterestedInQualityAudit: boolean;
  whatToolsUsedText: string;
}

const defaultFormValues: FeedSubmissionFormFormInput = {
  name: '',
  isOfficialProducer: '',
  dataType: 'GTFS Schedule',
  transitProviderName: '',
  feedLink: '',
  licensePath: '',
  country: '',
  region: '',
  municipality: '',
  tripUpdates: false,
  vehiclePositions: false,
  serviceAlerts: false,
  gtfsRealtimeLink: '',
  gtfsRelatedScheduleLink: '',
  note: '',
  isAuthRequired: 'no',
  dataProducerEmail: '',
  isInterestedInQualityAudit: false,
  whatToolsUsedText: '',
};

export default function FeedSubmissionForm({
  activeStep,
  handleNext,
  handleBack,
}: FeedSubmissionFormProps): React.ReactElement {
  const [formData, setFormData] =
    React.useState<FeedSubmissionFormFormInput>(defaultFormValues);

  const formStepSubmit = (
    partialFormData: Partial<FeedSubmissionFormFormInput>,
  ): void => {
    setFormData((prevData) => ({ ...prevData, ...partialFormData }));
    handleNext();
  };

  const formStepBack = (
    partialFormData: Partial<FeedSubmissionFormFormInput>,
  ): void => {
    setFormData((prevData) => ({ ...prevData, ...partialFormData }));
    handleBack();
  };

  const finalSubmit = (
    partialFormData: Partial<FeedSubmissionFormFormInput>,
  ): void => {
    const finalData = { ...formData, ...partialFormData };
    setFormData(finalData);
    // console.log('FINAL API CALL WITH', finalData);
    // TODO: API call with finalData
    // TODO: loading state of API call
    // TODO: feed submitted page
    handleNext();
  };

  return (
    <>
      {activeStep === 0 && (
        <FormFirstStep
          initialValues={formData}
          submitFormData={formStepSubmit}
        ></FormFirstStep>
      )}
      {activeStep === 1 && formData.dataType === 'GTFS Schedule' && (
        <FormSecondStep
          initialValues={formData}
          submitFormData={formStepSubmit}
          handleBack={formStepBack}
        ></FormSecondStep>
      )}
      {activeStep === 1 && formData.dataType === 'GTFS Realtime' && (
        <FormSecondStepRT
          initialValues={formData}
          submitFormData={formStepSubmit}
          handleBack={formStepBack}
        ></FormSecondStepRT>
      )}
      {activeStep === 2 && (
        <FormThirdStep
          initialValues={formData}
          submitFormData={finalSubmit}
          handleBack={formStepBack}
        ></FormThirdStep>
      )}
    </>
  );
}
