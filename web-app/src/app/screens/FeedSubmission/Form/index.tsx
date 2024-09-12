import React from 'react';
import FormFirstStep from './FirstStep';
import FormSecondStep from './SecondStep';
import FormSecondStepRT from './SecondStepRealtime';
import FormFourthStep from './FourthStep';
import {
  Stepper,
  Step,
  StepLabel,
  Box,
  CircularProgress,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import FormThirdStep from './ThirdStep';
import { submitNewFeedForm } from '../../../services/feeds/add-feed-form-service';
import { useTranslation } from 'react-i18next';

export type YesNoFormInput = 'yes' | 'no' | '';
export type AuthTypes =
  | 'None - 0'
  | 'API key - 1'
  | 'HTTP header - 2'
  | 'choiceRequired';

export interface FeedSubmissionFormFormInput {
  isOfficialProducer: YesNoFormInput;
  dataType: 'gtfs' | 'gtfs_rt';
  transitProviderName: string;
  feedLink?: string;
  oldFeedLink?: string;
  isUpdatingFeed?: YesNoFormInput;
  licensePath?: string;
  country?: string;
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
  tripUpdates: '',
  vehiclePositions: '',
  serviceAlerts: '',
  oldTripUpdates: '',
  oldVehiclePositions: '',
  oldServiceAlerts: '',
  gtfsRelatedScheduleLink: '',
  name: '',
  authType: 'None - 0',
  authSignupLink: '',
  authParameterName: '',
  dataProducerEmail: '',
  isInterestedInQualityAudit: '',
  userInterviewEmail: '',
  whatToolsUsedText: '',
  hasLogoPermission: '',
};

export default function FeedSubmissionForm(): React.ReactElement {
  const { t } = useTranslation('feeds');
  const [isSubmitLoading, setIsSubmitLoading] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<undefined | string>(
    undefined,
  );
  const [activeStep, setActiveStep] = React.useState(0);
  const [steps, setSteps] = React.useState(['', '', '']);
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
      setSteps(['', '', '', '']);
    } else {
      setSteps(['', '', '']);
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

  const finalSubmit = async (
    partialFormData: Partial<FeedSubmissionFormFormInput>,
  ): Promise<void> => {
    const finalData = { ...formData, ...partialFormData };
    setIsSubmitLoading(true);
    setFormData(finalData);
    try {
      const requestBody = { ...finalData };
      await submitNewFeedForm(requestBody);
      handleNext();
    } catch (error) {
      setSubmitError(t('form.errorSubmitting'));
    } finally {
      setIsSubmitLoading(false);
    }
  };

  if (isSubmitLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          flexWrap: 'wrap',
          mt: 3,
        }}
      >
        <CircularProgress />
        <Typography
          variant='h6'
          sx={{ width: '100%', textAlign: 'center', mt: 2 }}
        >
          {t('form.submittingFeed')}
        </Typography>
      </Box>
    );
  }

  if (submitError !== undefined) {
    return <Typography>{submitError}</Typography>;
  }

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
          submitFormData={(submittedFormData) => {
            if (activeStep === steps.length - 1) {
              void finalSubmit(submittedFormData);
            } else {
              formStepSubmit(submittedFormData);
            }
          }}
          handleBack={formStepBack}
        ></FormThirdStep>
      )}
      {activeStep === 3 && (
        <FormFourthStep
          initialValues={formData}
          submitFormData={(submittedFormData) => {
            void finalSubmit(submittedFormData);
          }}
          handleBack={formStepBack}
        ></FormFourthStep>
      )}
    </>
  );
}
