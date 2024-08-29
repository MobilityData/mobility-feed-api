import {
  Typography,
  Grid,
  FormControl,
  FormLabel,
  Button,
  TextField,
  MenuItem,
  Select,
  FormHelperText,
} from '@mui/material';
import {
  type SubmitHandler,
  Controller,
  useForm,
  useWatch,
} from 'react-hook-form';
import { type YesNoFormInput, type FeedSubmissionFormFormInput } from '.';

export interface FeedSubmissionFormInputThirdStep {
  dataProducerEmail?: string;
  isInterestedInQualityAudit: YesNoFormInput;
  userInterviewEmail?: string;
  hasLogoPermission: YesNoFormInput;
  whatToolsUsedText?: string;
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
      hasLogoPermission: initialValues.hasLogoPermission,
    },
  });
  const onSubmit: SubmitHandler<FeedSubmissionFormInputThirdStep> = (data) => {
    if (data.isInterestedInQualityAudit === 'no') {
      delete data.userInterviewEmail;
    }
    submitFormData(data);
  };

  const isInterestedInQualityAudit = useWatch({
    control,
    name: 'isInterestedInQualityAudit',
  });

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
            <FormControl
              component='fieldset'
              error={errors.isInterestedInQualityAudit !== undefined}
            >
              <FormLabel required>
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
                rules={{ required: 'Required' }}
                render={({ field }) => (
                  <>
                    <Select {...field} sx={{ width: '200px' }}>
                      <MenuItem value='yes'>Yes</MenuItem>
                      <MenuItem value='no'>No</MenuItem>
                    </Select>
                    <FormHelperText>
                      {errors.isInterestedInQualityAudit?.message ?? ''}
                    </FormHelperText>
                  </>
                )}
              />
            </FormControl>
          </Grid>
          {isInterestedInQualityAudit === 'yes' && (
            <Grid item>
              <FormControl
                component='fieldset'
                fullWidth
                error={errors.userInterviewEmail !== undefined}
              >
                <FormLabel required>Data quality audit contact email</FormLabel>
                <Controller
                  control={control}
                  name='userInterviewEmail'
                  rules={{ required: 'Contact email required' }}
                  render={({ field }) => (
                    <TextField
                      className='md-small-input'
                      {...field}
                      error={errors.userInterviewEmail !== undefined}
                      helperText={errors.userInterviewEmail?.message ?? ''}
                    />
                  )}
                />
              </FormControl>
            </Grid>
          )}
          <Grid item>
            <FormControl
              component='fieldset'
              error={errors.hasLogoPermission !== undefined}
            >
              <FormLabel required>
                Do we have your permission to use your logo?<br></br>
                <Typography variant='caption' color='textSecondary'>
                  This would be would be used to display your logo on the
                  Mobilitydatabase website
                </Typography>
              </FormLabel>
              <Controller
                control={control}
                name='hasLogoPermission'
                rules={{ required: 'Required' }}
                render={({ field }) => (
                  <>
                    <Select {...field} sx={{ width: '200px' }}>
                      <MenuItem value='yes'>Yes</MenuItem>
                      <MenuItem value='no'>No</MenuItem>
                    </Select>
                    <FormHelperText>
                      {errors.hasLogoPermission?.message ?? ''}
                    </FormHelperText>
                  </>
                )}
              />
            </FormControl>
          </Grid>
          <Grid item>
            <FormControl component='fieldset' fullWidth>
              <FormLabel>
                What tools do you use to create GTFS data?
                <br></br>
                <Typography variant='caption' color='textSecondary'>
                  Could include open source librareis, vendor serviecs, or other
                  applications.
                </Typography>
              </FormLabel>
              <Controller
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
