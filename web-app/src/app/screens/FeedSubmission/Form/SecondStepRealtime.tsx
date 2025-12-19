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
import { isValidFeedLink, checkFeedUrlExistsInCsv } from '../../../services/feeds/utils';

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
                rules={{
                  required: t('form.feedLinkRequired'),
                  validate: async (value) => {
                    if (!isValidFeedLink(value ?? '')) return t('form.errorUrl');
                    const exists = await checkFeedUrlExistsInCsv(value ?? '');
                    if (exists) {
                      return `Feed Exists:${exists}`;
                    }
                    return true;
                  },
                }}
                render={({ field }) => (
                  <TextField
                    className='md-small-input'
                    {...field}
                    error={errors.serviceAlerts !== undefined}
                    data-cy='serviceAlertFeed'
                    helperText={
                      errors.serviceAlerts?.message?.startsWith('Feed Exists:') ? (
                        <span>
                          {t('form.feedAlreadyExists')}
                          <a href=
                            {errors.serviceAlerts.message.replace('Feed Exists:', `https://mobilitydatabase.org/feeds/gtfs/`)} target="_blank" rel="noopener noreferrer">
                            {t(errors.serviceAlerts.message.replace('Feed Exists:',''))}
                          </a>
                        </span>
                      ) : (
                        errors.serviceAlerts?.message ?? ''
                      )
                    }
                  />
                )}
              />
            </FormControl>
          </Grid>
          {isFeedUpdate && (
            <Grid item mb={2}>
              <FormControl
                component='fieldset'
                fullWidth
                error={errors.oldServiceAlerts !== undefined}
              >
                <FormLabel component='legend'>
                  {t('oldServiceAlertsFeed')}
                </FormLabel>
                <Controller
                  control={control}
                  name='oldServiceAlerts'
                  rules={{
                    validate: (value) => {
                      if (value === '' || value === undefined) return true;
                      return isValidFeedLink(value) || t('form.errorUrl');
                    },
                  }}
                  render={({ field }) => (
                    <TextField
                      className='md-small-input'
                      {...field}
                      helperText={errors.oldServiceAlerts?.message ?? ''}
                      error={errors.oldServiceAlerts !== undefined}
                    />
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
                rules={{
                  required: t('form.feedLinkRequired'),
                  validate: async (value) => {
                    if (!isValidFeedLink(value ?? '')) return t('form.errorUrl');
                    const exists = await checkFeedUrlExistsInCsv(value ?? '');
                    if (exists) {
                      return `Feed Exists:${exists}`;
                    }
                    return true;
                  },
                }}
                render={({ field }) => (
                  <TextField
                    className='md-small-input'
                    {...field}
                    error={errors.tripUpdates !== undefined}
                    helperText={
                      errors.tripUpdates?.message?.startsWith('Feed Exists:') ? (
                        <span>
                          {t('form.feedAlreadyExists')}
                          <a href=
                            {errors.tripUpdates.message.replace('Feed Exists:', `https://mobilitydatabase.org/feeds/gtfs/`)} target="_blank" rel="noopener noreferrer">
                            {t(errors.tripUpdates.message.replace('Feed Exists:',''))}
                          </a>
                        </span>
                      ) : (
                        errors.tripUpdates?.message ?? ''
                      )
                    }
                  />
                )}
              />
            </FormControl>
          </Grid>
          {isFeedUpdate && (
            <Grid item mb={2}>
              <FormControl
                component='fieldset'
                fullWidth
                error={errors.oldTripUpdates !== undefined}
              >
                <FormLabel component='legend'>
                  {t('oldTripUpdatesFeed')}
                </FormLabel>
                <Controller
                  control={control}
                  name='oldTripUpdates'
                  rules={{
                    validate: (value) => {
                      if (value === '' || value === undefined) return true;
                      return isValidFeedLink(value) || t('form.errorUrl');
                    },
                  }}
                  render={({ field }) => (
                    <TextField
                      className='md-small-input'
                      {...field}
                      helperText={errors.oldTripUpdates?.message ?? ''}
                      error={errors.oldTripUpdates !== undefined}
                    />
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
                rules={{
                  required: t('form.feedLinkRequired'),
                  validate: async (value) => {
                    if (!isValidFeedLink(value ?? '')) return t('form.errorUrl');
                    const exists = await checkFeedUrlExistsInCsv(value ?? '');
                    if (exists) {
                      return `Feed Exists:${exists}`;
                    }
                    return true;
                  },
                }}
                render={({ field }) => (
                  <TextField
                    className='md-small-input'
                    {...field}
                    error={errors.vehiclePositions !== undefined}
                    helperText={
                      errors.vehiclePositions?.message?.startsWith('Feed Exists:') ? (
                        <span>
                          {t('form.feedAlreadyExists')}
                          <a href=
                            {errors.vehiclePositions.message.replace('Feed Exists:', `https://mobilitydatabase.org/feeds/gtfs/`)} target="_blank" rel="noopener noreferrer">
                            {t(errors.vehiclePositions.message.replace('Feed Exists:',''))}
                          </a>
                        </span>
                      ) : (
                        errors.vehiclePositions?.message ?? ''
                      )
                    }
                  />
                )}
              />
            </FormControl>
          </Grid>
          {isFeedUpdate && (
            <Grid item mb={2}>
              <FormControl
                component='fieldset'
                fullWidth
                error={errors.oldVehiclePositions !== undefined}
              >
                <FormLabel component='legend'>
                  {t('oldVehiclePositionsFeed')}
                </FormLabel>
                <Controller
                  control={control}
                  name='oldVehiclePositions'
                  rules={{
                    validate: (value) => {
                      if (value === '' || value === undefined) return true;
                      return isValidFeedLink(value) || t('form.errorUrl');
                    },
                  }}
                  render={({ field }) => (
                    <TextField
                      className='md-small-input'
                      {...field}
                      helperText={errors.oldVehiclePositions?.message ?? ''}
                      error={errors.oldVehiclePositions !== undefined}
                    />
                  )}
                />
              </FormControl>
            </Grid>
          )}

          <Grid item>
            <FormControl
              component='fieldset'
              fullWidth
              error={errors.gtfsRelatedScheduleLink !== undefined}
            >
              <FormLabel component='legend'>
                {t('relatedGtfsScheduleFeed')}
              </FormLabel>
              <Controller
                control={control}
                name='gtfsRelatedScheduleLink'
                rules={{
                  validate: (value) => {
                    if (value === '' || value === undefined) return true;
                    return isValidFeedLink(value) || t('form.errorUrl');
                  },
                }}
                render={({ field }) => (
                  <TextField
                    className='md-small-input'
                    {...field}
                    helperText={errors.gtfsRelatedScheduleLink?.message ?? ''}
                    error={errors.gtfsRelatedScheduleLink !== undefined}
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
