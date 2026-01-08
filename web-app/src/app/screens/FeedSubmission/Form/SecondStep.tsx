import {
  Typography,
  Grid,
  FormControl,
  FormLabel,
  Button,
  MenuItem,
  Select,
  TextField,
  FormHelperText,
} from '@mui/material';
import { Controller, type SubmitHandler, useForm } from 'react-hook-form';
import { type FeedSubmissionFormFormInput } from '.';
import { useTranslations } from 'next-intl';
import { getCountryDataList } from 'countries-list';
import { useState } from 'react';
import FormLabelDescription from './components/FormLabelDescription';

export interface FeedSubmissionFormInputSecondStep {
  country: string;
  region: string;
  municipality: string;
  name: string;
  licensePath?: string;
}

interface FormSecondStepProps {
  initialValues: FeedSubmissionFormFormInput;
  submitFormData: (formData: Partial<FeedSubmissionFormFormInput>) => void;
  handleBack: (formData: Partial<FeedSubmissionFormFormInput>) => void;
}

export default function FormSecondStep({
  initialValues,
  submitFormData,
  handleBack,
}: FormSecondStepProps): React.ReactElement {
  const [countryList] = useState(getCountryDataList());
  const t = useTranslations('feeds');
  const {
    control,
    handleSubmit,
    formState: { errors },
    getValues,
  } = useForm<FeedSubmissionFormInputSecondStep>({
    defaultValues: {
      country: initialValues.country,
      region: initialValues.region,
      municipality: initialValues.municipality,
      name: initialValues.name,
      licensePath: initialValues.licensePath,
    },
  });
  const onSubmit: SubmitHandler<FeedSubmissionFormInputSecondStep> = (data) => {
    submitFormData(data);
  };

  return (
    <>
      <Typography gutterBottom>{t('gtfsScheduleFeed')}</Typography>
      {/* eslint-disable-next-line @typescript-eslint/no-misused-promises */}
      <form onSubmit={handleSubmit(onSubmit)}>
        <Grid container direction={'column'} rowSpacing={2}>
          <Grid>
            <FormControl
              component='fieldset'
              error={errors.country !== undefined}
            >
              <FormLabel component='legend' required data-cy='countryLabel'>
                {t('common:country')}
              </FormLabel>
              <Controller
                rules={{ required: 'Country is required' }}
                control={control}
                name='country'
                render={({ field }) => (
                  <>
                    <Select
                      {...field}
                      displayEmpty
                      sx={{ minWidth: '250px' }}
                      data-cy='countryDropdown'
                    >
                      <MenuItem value={''}>
                        <em>{t('common:chooseCountry')}</em>
                      </MenuItem>
                      {countryList.map((country) => (
                        <MenuItem key={country.iso2} value={country.iso2}>
                          {country.name}
                        </MenuItem>
                      ))}
                    </Select>
                    <FormHelperText>
                      {errors.country?.message ?? ''}
                    </FormHelperText>
                  </>
                )}
              />
            </FormControl>
          </Grid>
          <Grid>
            <FormControl component='fieldset' fullWidth>
              <FormLabel component='legend'>{t('common:region')}</FormLabel>
              <Controller
                control={control}
                name='region'
                render={({ field }) => (
                  <TextField className='md-small-input' {...field} />
                )}
              />
            </FormControl>
          </Grid>
          <Grid>
            <FormControl component='fieldset' fullWidth>
              <FormLabel component='legend'>
                {t('common:municipality')}
              </FormLabel>
              <Controller
                control={control}
                name='municipality'
                render={({ field }) => (
                  <TextField className='md-small-input' {...field} />
                )}
              />
            </FormControl>
          </Grid>
          <Grid>
            <FormControl component='fieldset' fullWidth>
              <FormLabel component='legend'>{t('common:name')}</FormLabel>
              <FormLabelDescription>
                {t('feedNameDetails')}
              </FormLabelDescription>
              <Controller
                control={control}
                name='name'
                render={({ field }) => (
                  <TextField className='md-small-input' {...field} />
                )}
              />
            </FormControl>
          </Grid>
          <Grid>
            <FormControl
              component='fieldset'
              fullWidth
              error={errors.licensePath !== undefined}
            >
              <FormLabel component='legend'>{t('linkToLicense')}</FormLabel>
              <Controller
                rules={{
                  validate: (value) => {
                    if (value === '' || value === undefined) return true;
                    return /^https?:\/\//.test(value) || t('form.errorUrl');
                  },
                }}
                control={control}
                name='licensePath'
                render={({ field }) => (
                  <TextField
                    className='md-small-input'
                    {...field}
                    helperText={errors.licensePath?.message ?? ''}
                    error={errors.licensePath !== undefined}
                  />
                )}
              />
            </FormControl>
          </Grid>

          <Grid container spacing={2}>
            <Grid>
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
            <Grid>
              <Button
                type='submit'
                variant='contained'
                sx={{ mt: 3, mb: 2 }}
                data-cy='secondStepSubmit'
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
