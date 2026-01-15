import {
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
import { type FeedSubmissionFormFormInput, type AuthTypes } from '.';
import { useTranslations } from 'next-intl';
import { isValidFeedLink } from '../../../services/feeds/utils';
import FormLabelDescription from './components/FormLabelDescription';

export interface FeedSubmissionFormInputThirdStep {
  authType: AuthTypes;
  authSignupLink?: string;
  authParameterName?: string;
  emptyLicenseUsage?: string;
}

interface FormThirdStepProps {
  initialValues: FeedSubmissionFormFormInput;
  submitFormData: (formData: Partial<FeedSubmissionFormFormInput>) => void;
  handleBack: (formData: Partial<FeedSubmissionFormFormInput>) => void;
}

export default function FormThirdStep({
  initialValues,
  submitFormData,
  handleBack,
}: FormThirdStepProps): React.ReactElement {
  const t = useTranslations('feeds');
  const tCommon = useTranslations('common');
  const {
    control,
    handleSubmit,
    formState: { errors },
    getValues,
    setValue,
  } = useForm<FeedSubmissionFormInputThirdStep>({
    defaultValues: {
      authType: initialValues.authType,
      authSignupLink: initialValues.authSignupLink,
      authParameterName: initialValues.authParameterName,
    },
  });

  const authType = useWatch({
    control,
    name: 'authType',
  });

  const onSubmit: SubmitHandler<FeedSubmissionFormInputThirdStep> = (
    data,
  ): void => {
    submitFormData(data);
  };

  // Remove unused variables and fix strict boolean expressions
  const isOfficialProducer = initialValues.isOfficialProducer === 'yes';
  // Fix strict boolean expression for noLicenseProvided in conditional rendering
  const noLicenseProvided =
    initialValues.licensePath === null ||
    initialValues.licensePath === undefined ||
    initialValues.licensePath === '';

  return (
    <>
      {/* eslint-disable-next-line @typescript-eslint/no-misused-promises */}
      <form onSubmit={handleSubmit(onSubmit)}>
        <Grid container direction={'column'} rowSpacing={2}>
          {/* Show required emptyLicenseUsage if official producer and no license provided */}
          {isOfficialProducer && noLicenseProvided && (
            <Grid>
              <FormControl
                component='fieldset'
                fullWidth
                error={errors.emptyLicenseUsage !== undefined}
              >
                <FormLabel required data-cy='emptyLicenseUsageLabel'>
                  {t('emptyLicenseUsage')}
                </FormLabel>
                <Controller
                  control={control}
                  name='emptyLicenseUsage'
                  rules={{ required: tCommon('form.required') }}
                  render={({ field }) => (
                    <Select
                      {...field}
                      sx={{ width: '200px' }}
                      data-cy='emptyLicenseUsage'
                    >
                      <MenuItem value='yes'>{tCommon('form.yes')}</MenuItem>
                      <MenuItem value='no'>{tCommon('form.no')}</MenuItem>
                      <MenuItem value='unsure'>
                        {tCommon('form.notSure')}
                      </MenuItem>
                    </Select>
                  )}
                />
                <FormHelperText>
                  {errors.emptyLicenseUsage?.message ?? ''}
                </FormHelperText>
              </FormControl>
            </Grid>
          )}
          <Grid>
            <FormControl component='fieldset'>
              <FormLabel>{t('isAuthRequired')}</FormLabel>
              <FormLabelDescription>
                {t('isAuthRequiredDetails')}
              </FormLabelDescription>
              <Select
                value={authType === 'None - 0' ? authType : 'choiceRequired'}
                sx={{ width: '200px' }}
                onChange={(event) => {
                  setValue('authType', event.target.value as AuthTypes);
                }}
                data-cy='isAuthRequired'
              >
                <MenuItem value='choiceRequired'>
                  {tCommon('form.yes')}
                </MenuItem>
                <MenuItem value='None - 0'>{tCommon('form.no')}</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          {authType !== 'None - 0' && (
            <>
              <Grid>
                <FormControl
                  component='fieldset'
                  error={errors.authType !== undefined}
                >
                  <FormLabel required data-cy='authTypeLabel'>
                    {t('authenticationType')}
                  </FormLabel>
                  <Controller
                    control={control}
                    name='authType'
                    rules={{
                      required: tCommon('form.required'),
                      validate: (value) =>
                        value !== 'choiceRequired' ||
                        t('selectAuthenticationType'),
                    }}
                    render={({ field }) => (
                      <>
                        <Select {...field} sx={{ width: '200px' }}>
                          <MenuItem value='choiceRequired'>
                            <em>{tCommon('form.select')}</em>
                          </MenuItem>
                          <MenuItem value='API key - 1'>
                            {t('form.authType.apiKey')}
                          </MenuItem>
                          <MenuItem value='HTTP header - 2'>
                            {t('form.authType.httpHeader')}
                          </MenuItem>
                        </Select>
                        <FormHelperText>
                          {errors.authType?.message ?? ''}
                        </FormHelperText>
                      </>
                    )}
                  />
                </FormControl>
              </Grid>
              <Grid>
                <FormControl
                  component='fieldset'
                  fullWidth
                  error={errors.authSignupLink !== undefined}
                >
                  <FormLabel required data-cy='authSignupLabel'>
                    {t('form.authType.signUpLink')}
                  </FormLabel>
                  <Controller
                    control={control}
                    name='authSignupLink'
                    rules={{
                      required: tCommon('form.required'),
                      validate: (value) =>
                        isValidFeedLink(value ?? '') || t('form.errorUrl'),
                    }}
                    render={({ field }) => (
                      <TextField
                        className='md-small-input'
                        {...field}
                        helperText={errors.authSignupLink?.message ?? ''}
                        error={errors.authSignupLink !== undefined}
                      />
                    )}
                  />
                </FormControl>
              </Grid>
              <Grid>
                <FormControl component='fieldset' fullWidth>
                  <FormLabel>{t('form.authType.parameterName')}</FormLabel>
                  <FormLabelDescription>
                    {t('form.authType.parameterNameDetail')}
                  </FormLabelDescription>
                  <Controller
                    control={control}
                    name='authParameterName'
                    render={({ field }) => (
                      <TextField className='md-small-input' {...field} />
                    )}
                  />
                </FormControl>
              </Grid>
            </>
          )}

          <Grid container spacing={2}>
            <Grid>
              <Button
                onClick={() => {
                  handleBack(getValues());
                }}
                variant='outlined'
                sx={{ mt: 3, mb: 2 }}
              >
                {tCommon('back')}
              </Button>
            </Grid>
            <Grid>
              <Button
                type='submit'
                variant='contained'
                sx={{ mt: 3, mb: 2 }}
                data-cy='thirdStepSubmit'
              >
                {tCommon('next')}
              </Button>
            </Grid>
          </Grid>
        </Grid>
      </form>
    </>
  );
}
