import {
  Typography,
  Grid,
  FormControl,
  FormLabel,
  Button,
  TextField,
} from '@mui/material';
import { type SubmitHandler, Controller, useForm } from 'react-hook-form';
import { type AuthTypes, type FeedSubmissionFormFormInput } from '.';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

export interface FeedSubmissionFormInputSecondStepRT {
  tripUpdates: string;
  vehiclePositions: string;
  serviceAlerts: string;
  oldTripUpdates?: string;
  oldVehiclePositions?: string;
  oldServiceAlerts?: string;
  gtfsRelatedScheduleLink: string;
  licensePath?: string;
  authType: AuthTypes;
  authSignupLink?: string;
  authParameterName?: string;
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
  const { t } = useTranslation('feeds');
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitted },
    getValues,
    trigger,
    watch,
  } = useForm<FeedSubmissionFormInputSecondStepRT>({
    defaultValues: {
      tripUpdates: initialValues.tripUpdates,
      vehiclePositions: initialValues.vehiclePositions,
      serviceAlerts: initialValues.serviceAlerts,
      oldTripUpdates: initialValues.oldTripUpdates,
      oldVehiclePositions: initialValues.oldVehiclePositions,
      oldServiceAlerts: initialValues.oldServiceAlerts,
      gtfsRelatedScheduleLink: initialValues.gtfsRelatedScheduleLink,
    },
  });

  const isFeedUpdate = initialValues.isUpdatingFeed === 'yes';

  const onSubmit: SubmitHandler<FeedSubmissionFormInputSecondStepRT> = (
    data,
  ) => {
    submitFormData(data);
  };

  const [tripUpdates, vehiclePositions, serviceAlerts] = watch([
    'tripUpdates',
    'vehiclePositions',
    'serviceAlerts',
  ]);

  useEffect(() => {
    if (isSubmitted) {
      // assures that the error is updated for all
      void trigger(['tripUpdates', 'vehiclePositions', 'serviceAlerts']);
    }
  }, [tripUpdates, vehiclePositions, serviceAlerts]);

  const gtfsRtLinkValidation = (): undefined | string => {
    if (tripUpdates !== '' || vehiclePositions !== '' || serviceAlerts !== '') {
      return undefined;
    } else {
      return t('form.atLeastOneRealtimeFeed');
    }
  };

  return (
    <>
      <Typography
        sx={{
          fontSize: { xs: 12, sm: 18 },
        }}
      >
        {t('gtfsRealtimeFeed')}
      </Typography>
      {/* eslint-disable-next-line @typescript-eslint/no-misused-promises */}
      <form onSubmit={handleSubmit(onSubmit)}>
        <Grid container direction={'column'} rowSpacing={2}>
          <Grid item>
            <FormControl
              component='fieldset'
              fullWidth
              error={errors.serviceAlerts !== undefined}
            >
              <FormLabel component='legend' data-cy='serviceAlertFeedLabel'>
                {t('serviceAlertsFeed')}
              </FormLabel>
              <Controller
                control={control}
                name='serviceAlerts'
                rules={{ validate: gtfsRtLinkValidation }}
                render={({ field }) => (
                  <TextField
                    className='md-small-input'
                    {...field}
                    helperText={errors.serviceAlerts?.message ?? ''}
                    error={errors.serviceAlerts !== undefined}
                    data-cy='serviceAlertFeed'
                  />
                )}
              />
            </FormControl>
          </Grid>
          {isFeedUpdate && (
            <Grid item mb={2}>
              <FormControl component='fieldset' fullWidth>
                <FormLabel component='legend'>
                  {t('oldServiceAlertsFeed')}
                </FormLabel>
                <Controller
                  control={control}
                  name='oldServiceAlerts'
                  render={({ field }) => (
                    <TextField className='md-small-input' {...field} />
                  )}
                />
              </FormControl>
            </Grid>
          )}
          <Grid item>
            <FormControl
              component='fieldset'
              fullWidth
              error={errors.tripUpdates !== undefined}
            >
              <FormLabel component='legend' data-cy='tripUpdatesFeedLabel'>
                {t('tripUpdatesFeed')}
              </FormLabel>
              <Controller
                control={control}
                name='tripUpdates'
                rules={{ validate: gtfsRtLinkValidation }}
                render={({ field }) => (
                  <TextField
                    className='md-small-input'
                    {...field}
                    helperText={errors.tripUpdates?.message ?? ''}
                    error={errors.tripUpdates !== undefined}
                  />
                )}
              />
            </FormControl>
          </Grid>
          {isFeedUpdate && (
            <Grid item mb={2}>
              <FormControl component='fieldset' fullWidth>
                <FormLabel component='legend'>
                  {t('oldTripUpdatesFeed')}
                </FormLabel>
                <Controller
                  control={control}
                  name='oldTripUpdates'
                  render={({ field }) => (
                    <TextField className='md-small-input' {...field} />
                  )}
                />
              </FormControl>
            </Grid>
          )}
          <Grid item>
            <FormControl
              component='fieldset'
              fullWidth
              error={errors.vehiclePositions !== undefined}
            >
              <FormLabel component='legend' data-cy='vehiclePositionLabel'>
                {t('vehiclePositionsFeed')}
              </FormLabel>
              <Controller
                control={control}
                name='vehiclePositions'
                rules={{ validate: gtfsRtLinkValidation }}
                render={({ field }) => (
                  <TextField
                    className='md-small-input'
                    {...field}
                    helperText={errors.vehiclePositions?.message ?? ''}
                    error={errors.vehiclePositions !== undefined}
                  />
                )}
              />
            </FormControl>
          </Grid>
          {isFeedUpdate && (
            <Grid item mb={2}>
              <FormControl component='fieldset' fullWidth>
                <FormLabel component='legend'>
                  {t('oldVehiclePositionsFeed')}
                </FormLabel>
                <Controller
                  control={control}
                  name='oldVehiclePositions'
                  render={({ field }) => (
                    <TextField className='md-small-input' {...field} />
                  )}
                />
              </FormControl>
            </Grid>
          )}

          <Grid item>
            <FormControl component='fieldset' fullWidth>
              <FormLabel component='legend'>
                {t('relatedGtfsScheduleFeed')}
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
          <Grid container spacing={2}>
            <Grid item>
              <Button
                onClick={() => {
                  handleBack(getValues());
                }}
                variant='outlined'
                sx={{ mt: 3, mb: 2 }}
              >
                {t('common:back')}
              </Button>
            </Grid>
            <Grid item>
              <Button
                type='submit'
                variant='contained'
                sx={{ mt: 3, mb: 2 }}
                data-cy='secondStepRtSubmit'
              >
                {t('common:next')}
              </Button>
            </Grid>
          </Grid>
        </Grid>
      </form>
    </>
  );
}
