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
import { useTranslation } from 'react-i18next';
import { isValidFeedLink } from '../../../services/feeds/utils';
import FormLabelDescription from './components/FormLabelDescription';

export interface FeedSubmissionFormInputThirdStep {
  licensePath?: string;
  authType: AuthTypes;
  authSignupLink?: string;
  authParameterName?: string;
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
  const { t } = useTranslation('feeds');
  const {
    control,
    handleSubmit,
    formState: { errors },
    getValues,
    setValue,
  } = useForm<FeedSubmissionFormInputThirdStep>({
    defaultValues: {
      licensePath: initialValues.licensePath,
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

  return (
    <>
      {/* eslint-disable-next-line @typescript-eslint/no-misused-promises */}
      <form onSubmit={handleSubmit(onSubmit)}>
        <Grid container direction={'column'} rowSpacing={2}>
          <Grid item>
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
                    return isValidFeedLink(value) || t('form.errorUrl');
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
          <Grid item>
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
                  {t('common:form:yes')}
                </MenuItem>
                <MenuItem value='None - 0'>{t('common:form:no')}</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          {authType !== 'None - 0' && (
            <>
              <Grid item>
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
                      required: t('common:form.required'),
                      validate: (value) =>
                        value !== 'choiceRequired' ||
                        t('selectAuthenticationType'),
                    }}
                    render={({ field }) => (
                      <>
                        <Select {...field} sx={{ width: '200px' }}>
                          <MenuItem value='choiceRequired'>
                            <em>{t('common:form.select')}</em>
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
              <Grid item>
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
                      required: t('common:form.required'),
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
              <Grid item>
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
                data-cy='thirdStepSubmit'
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
