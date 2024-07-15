import {
  Typography,
  Grid,
  FormControl,
  FormLabel,
  Button,
  TextField,
  MenuItem,
  Select,
} from '@mui/material';
import { type SubmitHandler, Controller, useForm } from 'react-hook-form';
import { type FeedSubmissionFormFormInput } from '.';

export interface FeedSubmissionFormInputThirdStep {
  dataProducerEmail: string;
  isInterestedInQualityAudit: boolean;
  whatToolsUsedText: string;
}

interface FormSecondStepRTProps {
  initialValues: FeedSubmissionFormFormInput;
  submitFormData: (formData: Partial<FeedSubmissionFormFormInput>) => void;
  handleBack: (formData: Partial<FeedSubmissionFormFormInput>) => void;
}

export default function FormThirdStep({
  initialValues,
  submitFormData,
  handleBack,
}: FormSecondStepRTProps): React.ReactElement {
  const {
    control,
    handleSubmit,
    formState: { errors },
    getValues,
  } = useForm<FeedSubmissionFormInputThirdStep>({
    defaultValues: {
      dataProducerEmail: initialValues.dataProducerEmail,
      isInterestedInQualityAudit: initialValues.isInterestedInQualityAudit,
      whatToolsUsedText: initialValues.whatToolsUsedText,
    },
  });
  const onSubmit: SubmitHandler<FeedSubmissionFormInputThirdStep> = (data) => {
    submitFormData(data);
  };
  return (
    <>
      {/* eslint-disable-next-line @typescript-eslint/no-misused-promises */}
      <form onSubmit={handleSubmit(onSubmit)}>
        <Grid container direction={'column'} rowSpacing={2}>
          <Grid item>
            <FormControl
              component='fieldset'
              fullWidth
              error={errors.dataProducerEmail !== undefined}
            >
              <FormLabel component='legend' required>
                Data Producer Email<br></br>
                <Typography variant='caption' color='textSecondary'>
                  This is an official email that consumers of the feed can
                  contact to ask questions.
                </Typography>
              </FormLabel>
              <Controller
                rules={{ required: 'Data producer email required' }}
                control={control}
                name='dataProducerEmail'
                render={({ field }) => (
                  <TextField
                    className='md-small-input'
                    {...field}
                    error={errors.dataProducerEmail !== undefined}
                    helperText={errors.dataProducerEmail?.message ?? ''}
                  />
                )}
              />
            </FormControl>
          </Grid>
          <Grid item>
            {/* TODO: UX design decisionz: dropdown or radio buttons? */}
            {/* <FormControl component='fieldset'>
                <FormLabel component='legend'>
                  Are you interested in a data quality audit?
                  <Typography sx={{ fontSize: 12 }} gutterBottom>
                    This is a 1 time meeting with MobilityData to review your
                    GTFS validation report and discuss possible improvements.
                  </Typography>
                </FormLabel>
                <Controller
                  control={control}
                  name='isInterestedInQualityAudit'
                  render={({ field }) => (
                    <RadioGroup {...field}>
                      <FormControlLabel
                        value='yes'
                        control={<Radio />}
                        label='Yes'
                      />
                      <FormControlLabel
                        value='no'
                        control={<Radio />}
                        label='No'
                      />
                    </RadioGroup>
                  )}
                />
              </FormControl> */}
            <FormControl component='fieldset'>
              <FormLabel>
                Are you interested in a data quality audit?
                <br></br>
                <Typography variant='caption' color='textSecondary'>
                  This is a 1 time meeting with MobilityData to review your GTFS
                  validation report and discuss possible improvements.
                </Typography>
              </FormLabel>
              <Controller
                control={control}
                name='isInterestedInQualityAudit'
                render={({ field }) => (
                  <Select {...field}>
                    {/* TODO: revisit type - should be boolean */}
                    <MenuItem value={'false'}>No</MenuItem>
                    <MenuItem value={'true'}>Yes</MenuItem>
                  </Select>
                )}
              />
            </FormControl>
          </Grid>
          <Grid item>
            <FormControl component='fieldset'>
              <FormLabel component='legend'>
                What tools do you use to create GTFS data? Could include open
                source libraries, vendor services, or other applications.
              </FormLabel>
              <Controller
                rules={{ required: true }}
                control={control}
                name='whatToolsUsedText'
                render={({ field }) => (
                  <TextField
                    multiline
                    rows={3}
                    className='md-small-input'
                    {...field}
                  />
                )}
              />
            </FormControl>
          </Grid>

          <Grid container spacing={2}>
            <Grid item>
              <Button
                onClick={() => {
                  handleBack(getValues());
                }}
                variant='outlined'
                sx={{ mt: 3, mb: 2 }}
              >
                Back
              </Button>
            </Grid>
            <Grid item>
              <Button type='submit' variant='contained' sx={{ mt: 3, mb: 2 }}>
                Submit
              </Button>
            </Grid>
          </Grid>
        </Grid>
      </form>
    </>
  );
}
