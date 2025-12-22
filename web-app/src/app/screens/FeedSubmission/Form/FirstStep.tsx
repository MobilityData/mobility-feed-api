import {
  Grid,
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
  Select,
  MenuItem,
  Button,
  TextField,
  FormHelperText,
} from '@mui/material';

import {
  type SubmitHandler,
  Controller,
  useForm,
  useWatch,
} from 'react-hook-form';
import { type YesNoFormInput, type FeedSubmissionFormFormInput } from '.';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { isValidFeedLink, checkFeedUrlExistsInCsv, } from '../../../services/feeds/utils';
import FormLabelDescription from './components/FormLabelDescription';

export interface FeedSubmissionFormFormInputFirstStep {
  isOfficialProducer: YesNoFormInput;
  isOfficialFeed: 'yes' | 'no' | 'unsure' | undefined;
  dataType: 'gtfs' | 'gtfs_rt';
  transitProviderName?: string;
  feedLink?: string;
  oldFeedLink?: string;
  isUpdatingFeed: YesNoFormInput;
  unofficialDesc?: string;
  updateFreq?: string;
}

interface FormFirstStepProps {
  initialValues: FeedSubmissionFormFormInput;
  submitFormData: (formData: Partial<FeedSubmissionFormFormInput>) => void;
  setNumberOfSteps: (numberOfSteps: YesNoFormInput) => void;
}

const realtimeFeedURLPrefix = 'https://mobilitydatabase.org/feeds/gtfs/';

export default function FormFirstStep({
  initialValues,
  submitFormData,
  setNumberOfSteps,
}: FormFirstStepProps): React.ReactElement {
  const { t } = useTranslation('feeds');
  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<FeedSubmissionFormFormInputFirstStep>({
    defaultValues: {
      isOfficialProducer: initialValues.isOfficialProducer,
      isOfficialFeed: initialValues.isOfficialFeed,
      dataType: initialValues.dataType,
      transitProviderName: initialValues.transitProviderName,
      feedLink: initialValues.feedLink,
      oldFeedLink: initialValues.oldFeedLink,
      isUpdatingFeed: initialValues.isUpdatingFeed,
      unofficialDesc: initialValues.unofficialDesc,
      updateFreq: initialValues.updateFreq,
    },
  });

  const onSubmit: SubmitHandler<FeedSubmissionFormFormInputFirstStep> = (
    data,
  ): void => {
    if (data.dataType === 'gtfs_rt') {
      delete data.feedLink;
      delete data.oldFeedLink;
    }

    if (data.dataType === 'gtfs' && data.isUpdatingFeed === 'no') {
      delete data.oldFeedLink;
    }
    submitFormData(data);
  };

  const dataType = useWatch({
    control,
    name: 'dataType',
  });

  const isUpdatingFeed = useWatch({
    control,
    name: 'isUpdatingFeed',
  });

  const isOfficialProducer = useWatch({
    control,
    name: 'isOfficialProducer',
  });

  const isOfficialFeed = useWatch({
    control,
    name: 'isOfficialFeed',
  });

  useEffect(() => {
    setNumberOfSteps(isOfficialProducer);
  }, [isOfficialProducer]);

  return (
    <>
      {/* eslint-disable-next-line @typescript-eslint/no-misused-promises */}
      <form onSubmit={handleSubmit(onSubmit)}>
        <Grid container direction={'column'} rowSpacing={2}>
          <Grid item>
            <FormControl
              component='fieldset'
              error={errors.isOfficialProducer !== undefined}
            >
              <FormLabel required data-cy='isOfficialProducerLabel'>
                {t('areYouOfficialProducer')}
              </FormLabel>
              <Controller
                rules={{ required: t('common:form.required') }}
                control={control}
                name='isOfficialProducer'
                render={({ field }) => (
                  <>
                    <RadioGroup {...field}>
                      <FormControlLabel
                        value='yes'
                        control={<Radio />}
                        label={t('common:form.yes')}
                        data-cy='isOfficialProducerYes'
                      />
                      <FormControlLabel
                        value='no'
                        control={<Radio />}
                        label={t('common:form.no')}
                        data-cy='isOfficialProducerNo'
                      />
                    </RadioGroup>
                    <FormHelperText>
                      {errors.isOfficialProducer?.message ?? ''}
                    </FormHelperText>
                  </>
                )}
              />
            </FormControl>
          </Grid>
          <Grid item sx={{ '&.MuiGrid-item': { pt: '4px' } }}>
            <FormControl
              component='fieldset'
              error={errors.isOfficialFeed !== undefined}
            >
              <FormLabel required data-cy='isOfficialFeedLabel'>
                {t('isOfficialSource')}
              </FormLabel>
              <FormLabelDescription>
                {t('isOfficialSourceDetails')}
              </FormLabelDescription>
              <Controller
                rules={{ required: t('form.isOfficialFeedRequired') }}
                control={control}
                name='isOfficialFeed'
                render={({ field }) => (
                  <>
                    <Select
                      {...field}
                      data-cy='isOfficialFeed'
                      sx={{ width: '200px' }}
                    >
                      <MenuItem value={'yes'}>{t('common:form.yes')}</MenuItem>
                      <MenuItem value={'no'}>{t('common:form.no')}</MenuItem>
                      <MenuItem value={'unsure'}>
                        {t('common:form.notSure')}
                      </MenuItem>
                    </Select>
                    <FormHelperText>
                      {errors.isOfficialFeed?.message ?? ''}
                    </FormHelperText>
                  </>
                )}
              />
            </FormControl>
          </Grid>

          {/* New fields for unofficial feeds, moved right after isOfficialFeed */}
          {isOfficialFeed === 'no' && (
            <>
              <Grid item>
                <FormControl component='fieldset' fullWidth>
                  <FormLabel>{t('form.unofficialDesc')}</FormLabel>
                  <Controller
                    control={control}
                    name='unofficialDesc'
                    render={({ field }) => (
                      <TextField
                        {...field}
                        className='md-small-input'
                        multiline
                        minRows={2}
                        placeholder={t('form.unofficialDescPlaceholder')}
                        data-cy='unofficialDesc'
                      />
                    )}
                  />
                </FormControl>
              </Grid>
              <Grid item>
                <FormControl component='fieldset' fullWidth>
                  <FormLabel>{t('form.updateFreq')}</FormLabel>
                  <Controller
                    control={control}
                    name='updateFreq'
                    render={({ field }) => (
                      <TextField
                        {...field}
                        className='md-small-input'
                        placeholder={t('form.updateFreqPlaceholder')}
                        data-cy='updateFreq'
                      />
                    )}
                  />
                </FormControl>
              </Grid>
            </>
          )}
          <Grid item>
            <FormControl component='fieldset'>
              <FormLabel required>{t('dataType')}</FormLabel>
              <Controller
                control={control}
                name='dataType'
                render={({ field }) => (
                  <Select {...field} data-cy='dataType' sx={{ width: '200px' }}>
                    <MenuItem value={'gtfs'}>
                      {t('common:gtfsSchedule')}
                    </MenuItem>
                    <MenuItem value={'gtfs_rt'}>
                      {t('common:gtfsRealtime')}
                    </MenuItem>
                  </Select>
                )}
              />
            </FormControl>
          </Grid>
          <Grid item>
            <FormControl component='fieldset' fullWidth>
              <FormLabel>{t('transitProviderName')}</FormLabel>
              <Controller
                control={control}
                name='transitProviderName'
                render={({ field }) => (
                  <TextField {...field} className='md-small-input' />
                )}
              />
            </FormControl>
          </Grid>
          {dataType === 'gtfs' && (
            <Grid item>
              <FormControl
                component='fieldset'
                fullWidth
                error={errors.feedLink !== undefined}
              >
                <FormLabel component='legend' required data-cy='feedLinkLabel'>
                  {t('feedLink')}
                </FormLabel>
                <Controller
                  rules={{
                    required: t('form.feedLinkRequired'),
                    validate: async (value) => {
                      if (!isValidFeedLink(value ?? '')) {
                        return t('form.errorUrl');
                      }
                      const exists = await checkFeedUrlExistsInCsv(value ?? '');
                      if (typeof exists === 'string' && exists.length > 0) {
                        return `Feed Exists:${exists}`;
                      }
                      return true;
                    },
                  }}
                  control={control}
                  name='feedLink'
                  render={({ field }) => (
                    <TextField
                      data-cy='feedLink'
                      className='md-small-input'
                      error={errors.feedLink !== undefined}
                      {...field}
                      helperText={
                        typeof errors.feedLink?.message === 'string' && errors.feedLink.message.startsWith('Feed Exists:') ? (
                          <span>
                            {t('form.feedAlreadyExists')}
                            <a
                              href={errors.feedLink.message.replace('Feed Exists:', `${realtimeFeedURLPrefix}`)}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {t(errors.feedLink.message.replace('Feed Exists:', ''))}
                            </a>
                          </span>
                        ) : (
                          errors.feedLink?.message ?? ''
                        )
                      }
                    />
                  )}
                />
              </FormControl>
            </Grid>
          )}

          <Grid item>
            <FormControl
              component='fieldset'
              error={errors.dataType !== undefined}
            >
              <FormLabel required>{t('areYouUpdatingFeed')}</FormLabel>
              <Controller
                rules={{ required: t('common:form.required') }}
                control={control}
                name='isUpdatingFeed'
                render={({ field }) => (
                  <Select
                    {...field}
                    sx={{ width: '200px' }}
                    data-cy='isUpdatingFeed'
                  >
                    <MenuItem value={'yes'}>{t('common:form.yes')}</MenuItem>
                    <MenuItem value={'no'}>{t('common:form.no')}</MenuItem>
                  </Select>
                )}
              />
            </FormControl>
          </Grid>
          {dataType === 'gtfs' && isUpdatingFeed === 'yes' && (
            <Grid item>
              <FormControl
                component='fieldset'
                fullWidth
                error={errors.oldFeedLink !== undefined}
              >
                <FormLabel component='legend' required data-cy='oldFeedLabel'>
                  {t('oldFeedLink')}
                </FormLabel>
                <Controller
                  rules={{
                    required: t('form.oldFeedLinkRequired'),
                    validate: (value) =>
                      isValidFeedLink(value ?? '') || t('form.errorUrl'),
                  }}
                  control={control}
                  name='oldFeedLink'
                  render={({ field }) => (
                    <TextField
                      className='md-small-input'
                      data-cy='oldFeedLink'
                      helperText={errors.oldFeedLink?.message ?? ''}
                      error={errors.oldFeedLink !== undefined}
                      {...field}
                    />
                  )}
                />
              </FormControl>
            </Grid>
          )}

          <Grid container spacing={2}>
            <Grid item>
              <Button
                type='submit'
                variant='contained'
                sx={{ mt: 3, mb: 2 }}
                data-cy='submitFirstStep'
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
