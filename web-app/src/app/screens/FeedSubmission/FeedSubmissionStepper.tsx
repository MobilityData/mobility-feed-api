import * as React from 'react';
import Box from '@mui/material/Box';
import Stepper from '@mui/material/Stepper';
import Step from '@mui/material/Step';
import StepLabel from '@mui/material/StepLabel';
import FeedSubmissionForm from './Form';
import { useNavigate } from 'react-router-dom';

const steps = ['', '', ''];

export default function FeedSubmissionStepper(): React.ReactElement {
  const [activeStep, setActiveStep] = React.useState(0);
  const navigateTo = useNavigate();

  const handleNext = (): void => {
    const nextStep = activeStep + 1;
    setActiveStep(nextStep);
    if (nextStep === steps.length) {
      navigateTo('/contribute/submitted');
    }
  };

  const handleBack = (): void => {
    setActiveStep((prevActiveStep) => prevActiveStep - 1);
  };

  return (
    <Box sx={{ width: '100%', px: 5 }}>
      <Stepper activeStep={activeStep} sx={{ mb: 3 }}>
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

      <FeedSubmissionForm
        activeStep={activeStep}
        handleBack={handleBack}
        handleNext={handleNext}
      />
    </Box>
  );
}
