import {
  Typography,
  Grid,
  FormControl,
  FormLabel,
  FormControlLabel,
  Checkbox,
  RadioGroup,
  Radio,
  Button,
  TextField,
} from '@mui/material';
import { type SubmitHandler, Controller, useForm } from 'react-hook-form';
import { type FeedSubmissionFormFormInput } from '.';

export interface FeedSubmissionFormInputSecondStepRT {
  tripUpdates: boolean;
  vehiclePositions: boolean;
  serviceAlerts: boolean;
  gtfsRealtimeLink: string;
  gtfsRelatedScheduleLink: string;
  note: string;
  isAuthRequired: string;
}

interface FormSecondStepRTProps {
  initialValues: FeedSubmissionFormFormInput;
  submitFormData: (formData: Partial<FeedSubmissionFormFormInput>) => void;
  handleBack: (formData: Partial<FeedSubmissionFormFormInput>) => void;
}

export default function FormSecondStepRT({
  initialValues,
  submitFormData,
  handleBack,
}: FormSecondStepRTProps): React.ReactElement {
  const {
    control,
    handleSubmit,
    formState: { errors },
    getValues,
  } = useForm<FeedSubmissionFormInputSecondStepRT>({
    defaultValues: {
      tripUpdates: initialValues.tripUpdates,
      vehiclePositions: initialValues.vehiclePositions,
      serviceAlerts: initialValues.serviceAlerts,
      gtfsRealtimeLink: initialValues.gtfsRealtimeLink,
      gtfsRelatedScheduleLink: initialValues.gtfsRelatedScheduleLink,
      note: initialValues.note,
      isAuthRequired: initialValues.isAuthRequired,
    },
  });

  const onSubmit: SubmitHandler<FeedSubmissionFormInputSecondStepRT> = (
    data,
  ) => {
    submitFormData(data);
  };

  const entityTypeCheckBoxLabels = {
    tripUpdates: 'Trip Updates',
    vehiclePositions: 'Vehicle Positions',
    serviceAlerts: 'Service Alerts',
  };

  return (
    <>
      <Typography
        sx={{
          fontSize: { xs: 12, sm: 18 },
        }}
      >
        GTFS Realtime Feed
      </Typography>
      {/* eslint-disable-next-line @typescript-eslint/no-misused-promises */}
      <form onSubmit={handleSubmit(onSubmit)}>
        <Grid container direction={'column'} rowSpacing={2}>
          <Grid item>
            <FormControl component='fieldset'>
              <FormLabel component='legend'>Entity Type</FormLabel>
              {(
                ['tripUpdates', 'vehiclePositions', 'serviceAlerts'] as const
              ).map((entityType) => (
                <Controller
                  key={entityType}
                  control={control}
                  name={entityType}
                  render={({ field }) => {
                    return (
                      <FormControlLabel
                        control={<Checkbox />}
                        label={entityTypeCheckBoxLabels[entityType]}
                      />
                    );
                  }}
                />
              ))}
            </FormControl>
          </Grid>
          <Grid item>
            <FormControl
              component='fieldset'
              fullWidth
              required
              error={errors.gtfsRelatedScheduleLink !== undefined}
            >
              <FormLabel component='legend'>GTFS Realtime feed link</FormLabel>
              <Controller
                control={control}
                name='gtfsRealtimeLink'
                render={({ field }) => (
                  <TextField className='md-small-input' {...field} />
                )}
              />
            </FormControl>
          </Grid>
          <Grid item>
            <FormControl component='fieldset' fullWidth>
              <FormLabel component='legend'>
                Link to related GTFS Schedule feed
              </FormLabel>
              <Controller
                control={control}
                name='gtfsRelatedScheduleLink'
                render={({ field }) => (
                  <TextField className='md-small-input' {...field} />
                )}
              />
            </FormControl>
          </Grid>
          <Grid item>
            <FormControl component='fieldset' fullWidth>
              <FormLabel component='legend'>Note</FormLabel>
              <Controller
                control={control}
                name='note'
                render={({ field }) => (
                  <TextField
                    className='md-small-input'
                    {...field}
                    helperText='e.g “Aggregate” or “only contains Trip Updates and Vehicle
                Positions”'
                  />
                )}
              />
            </FormControl>
          </Grid>
          <Grid item>
            <FormControl component='fieldset'>
              <FormLabel component='legend'>
                Is authentication required?
              </FormLabel>
              <Controller
                control={control}
                name='isAuthRequired'
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
                Next
              </Button>
            </Grid>
          </Grid>
        </Grid>
      </form>
    </>
  );
}
