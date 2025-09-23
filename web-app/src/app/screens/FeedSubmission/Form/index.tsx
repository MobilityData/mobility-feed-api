import React, { useEffect } from 'react';
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
import { useNavigate, useSearchParams } from 'react-router-dom';
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
  isOfficialFeed: 'yes' | 'no' | 'unsure' | undefined;
  dataType: 'gtfs' | 'gtfs_rt';
  transitProviderName: string;
  feedLink?: string;
  oldFeedLink?: string;
  isUpdatingFeed?: YesNoFormInput;
  licensePath?: string;
  // Selected SPDX license id from ThirdStep selector (mock/demo)
  licenseSpdxId?: string | null;
  // Custom license builder (mock/demo only, not sent to backend)
  customLicenseEnabled?: boolean;
  customLicensePermissions?: string[];
  customLicenseConditions?: string[];
  customLicenseLimitations?: string[];
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
  unofficialDesc?: string; // Why was this feed created?
  updateFreq?: string; // How often is this feed updated?
  emptyLicenseUsage?: string; // Confirm usage if no license and official
}

const defaultFormValues: FeedSubmissionFormFormInput = {
  isOfficialProducer: '',
  isOfficialFeed: undefined,
  dataType: 'gtfs',
  transitProviderName: '',
  feedLink: '',
  oldFeedLink: '',
  isUpdatingFeed: 'no',
  licensePath: '',
  licenseSpdxId: null,
  customLicenseEnabled: false,
  customLicensePermissions: [],
  customLicenseConditions: [],
  customLicenseLimitations: [],
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
  unofficialDesc: '',
  updateFreq: '',
  emptyLicenseUsage: '',
};

export default function FeedSubmissionForm(): React.ReactElement {
  const { t } = useTranslation('feeds');
  const [searchParams, setSearchParams] = useSearchParams();
  const [isSubmitLoading, setIsSubmitLoading] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<undefined | string>(
    undefined,
  );
  const [steps, setSteps] = React.useState(['', '', '']);
  const navigateTo = useNavigate();
  const [formData, setFormData] =
    React.useState<FeedSubmissionFormFormInput>(defaultFormValues);
  const [stepsCompleted, setStepsCompleted] = React.useState({
    '1': false,
    '2': false,
    '3': false,
  });

  const currentStep =
    searchParams.get('step') === null ? 1 : Number(searchParams.get('step'));

  // route guards
  useEffect(() => {
    const step = searchParams.get('step') ?? '1';

    if (step === '2' || step === '3' || step === '4') {
      if (!stepsCompleted['1']) {
        setSearchParams({});
      }
      return;
    }

    if (step === '3' || step === '4') {
      if (!stepsCompleted['2']) {
        setSearchParams({ step: '1' });
      }
      return;
    }

    if (step === '4') {
      if (!stepsCompleted['3'] || !(formData.isOfficialProducer === 'yes')) {
        setSearchParams({ step: '3' });
      }
      return;
    }
    setSubmitError(undefined);
  }, [searchParams]);

  const handleNext = (): void => {
    const nextStep =
      searchParams.get('step') === null
        ? 2
        : Number(searchParams.get('step')) + 1;
    setStepsCompleted({ ...stepsCompleted, [currentStep]: true });
    setSearchParams({ step: nextStep.toString() });
    if (nextStep === steps.length + 1) {
      navigateTo('/contribute/submitted');
    }
  };

  const handleBack = (): void => {
    const previousStep = (currentStep - 1).toString();
    if (previousStep === '1') {
      setSearchParams({});
    } else {
      setSearchParams({ step: previousStep });
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
      // Do not send mock/demo-only fields to the backend
      const {
        licenseSpdxId: _omitLicenseSpdxId,
        customLicenseEnabled: _omitCustomEnabled,
        customLicensePermissions: _omitCustomPerms,
        customLicenseConditions: _omitCustomConds,
        customLicenseLimitations: _omitCustomLims,
        ...requestBody
      } = finalData;
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
        activeStep={currentStep - 1}
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
      {currentStep === 1 && (
        <FormFirstStep
          initialValues={formData}
          submitFormData={formStepSubmit}
          setNumberOfSteps={setNumberOfSteps}
        ></FormFirstStep>
      )}
      {currentStep === 2 && formData.dataType === 'gtfs' && (
        <FormSecondStep
          initialValues={formData}
          submitFormData={formStepSubmit}
          handleBack={formStepBack}
        ></FormSecondStep>
      )}
      {currentStep === 2 && formData.dataType === 'gtfs_rt' && (
        <FormSecondStepRT
          initialValues={formData}
          submitFormData={formStepSubmit}
          handleBack={formStepBack}
        ></FormSecondStepRT>
      )}
      {currentStep === 3 && (
        <FormThirdStep
          initialValues={formData}
          submitFormData={(submittedFormData) => {
            if (currentStep === steps.length) {
              void finalSubmit(submittedFormData);
            } else {
              formStepSubmit(submittedFormData);
            }
          }}
          handleBack={formStepBack}
        ></FormThirdStep>
      )}
      {currentStep === 4 && (
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
