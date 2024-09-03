import React from 'react';
import FormFirstStep from './FirstStep';
import FormSecondStep from './SecondStep';
import FormSecondStepRT from './SecondStepRealtime';
import FormThirdStep from './ThirdStep';
import { Stepper, Step, StepLabel } from '@mui/material';
import { useNavigate } from 'react-router-dom';

export type YesNoFormInput = 'yes' | 'no' | '';

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
  isOfficialProducer: YesNoFormInput;
  dataType: string;
  transitProviderName: string;
  feedLink: string;
  oldFeedLink?: string;
  isUpdatingFeed?: YesNoFormInput;
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
  isInterestedInQualityAudit: YesNoFormInput;
  userInterviewEmail?: string;
  whatToolsUsedText?: string;
  hasLogoPermission: YesNoFormInput;
}

const defaultFormValues: FeedSubmissionFormFormInput = {
  isOfficialProducer: '',
  dataType: 'gtfs',
  transitProviderName: '',
  feedLink: '',
  oldFeedLink: '',
  isUpdatingFeed: 'no',
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
  isInterestedInQualityAudit: '',
  userInterviewEmail: '',
  whatToolsUsedText: '',
  hasLogoPermission: '',
};

export default function FeedSubmissionForm(): React.ReactElement {
  const [activeStep, setActiveStep] = React.useState(0);
  const [steps, setSteps] = React.useState(['', '']);
  const navigateTo = useNavigate();
  const [formData, setFormData] =
    React.useState<FeedSubmissionFormFormInput>(defaultFormValues);

  const handleBack = (): void => {
    setActiveStep((prevActiveStep) => prevActiveStep - 1);
  };

  const handleNext = (): void => {
    const nextStep = activeStep + 1;
    setActiveStep(nextStep);
    if (nextStep === steps.length) {
      navigateTo('/contribute/submitted');
    }
  };

  const setNumberOfSteps = (isOfficialProducer: YesNoFormInput): void => {
    if (isOfficialProducer === 'yes') {
      setSteps(['', '', '']);
    } else {
      setSteps(['', '']);
    }
  };

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
      <Stepper
        activeStep={activeStep}
        sx={{ mb: 3, width: steps.length === 2 ? 'calc(50% + 24px)' : '100%' }}
      >
        {steps.map((label, index) => {
          const stepProps: { completed?: boolean } = {};
          const labelProps: {
            optional?: React.ReactNode;
          } = {};
          return (
            <Step key={index} {...stepProps}>
              <StepLabel {...labelProps}>{label}</StepLabel>
            </Step>
          );
        })}
      </Stepper>
      {activeStep === 0 && (
        <FormFirstStep
          initialValues={formData}
          submitFormData={formStepSubmit}
          setNumberOfSteps={setNumberOfSteps}
        ></FormFirstStep>
      )}
      {activeStep === 1 && formData.dataType === 'gtfs' && (
        <FormSecondStep
          initialValues={formData}
          submitFormData={formStepSubmit}
          handleBack={formStepBack}
        ></FormSecondStep>
      )}
      {activeStep === 1 && formData.dataType === 'gtfs_rt' && (
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
