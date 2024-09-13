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
import { useTranslation } from 'react-i18next';

export interface FeedSubmissionFormInputFourthStep {
  dataProducerEmail?: string;
  isInterestedInQualityAudit: YesNoFormInput;
  userInterviewEmail?: string;
  hasLogoPermission: YesNoFormInput;
  whatToolsUsedText?: string;
}

interface FormFourthStepProps {
  initialValues: FeedSubmissionFormFormInput;
  submitFormData: (formData: Partial<FeedSubmissionFormFormInput>) => void;
  handleBack: (formData: Partial<FeedSubmissionFormFormInput>) => void;
}

export default function FormFourthStep({
  initialValues,
  submitFormData,
  handleBack,
}: FormFourthStepProps): React.ReactElement {
  const { t } = useTranslation('feeds');
  const {
    control,
    handleSubmit,
    formState: { errors },
    getValues,
  } = useForm<FeedSubmissionFormInputFourthStep>({
    defaultValues: {
      dataProducerEmail: initialValues.dataProducerEmail,
      isInterestedInQualityAudit: initialValues.isInterestedInQualityAudit,
      whatToolsUsedText: initialValues.whatToolsUsedText,
      hasLogoPermission: initialValues.hasLogoPermission,
      userInterviewEmail: initialValues.userInterviewEmail,
    },
  });
  const onSubmit: SubmitHandler<FeedSubmissionFormInputFourthStep> = (data) => {
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
                {t('dataProducerEmail')}
                <br></br>
                <Typography variant='caption' color='textSecondary'>
                  {t('dataProducerEmailDetails')}
                </Typography>
              </FormLabel>
              <Controller
                rules={{ required: t('form.dataProducerEmailRequired') }}
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
                {t('interestedInDataAudit')}
                <br></br>
                <Typography variant='caption' color='textSecondary'>
                  {t('interestedInDataAuditDetails')}
                </Typography>
              </FormLabel>
              <Controller
                control={control}
                name='isInterestedInQualityAudit'
                rules={{ required: t('common:form.required') }}
                render={({ field }) => (
                  <>
                    <Select {...field} sx={{ width: '200px' }}>
                      <MenuItem value='yes'>{t('common:form:yes')}</MenuItem>
                      <MenuItem value='no'>{t('common:form:no')}</MenuItem>
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
                <FormLabel required>{t('dataAuditContactEmail')}</FormLabel>
                <Controller
                  control={control}
                  name='userInterviewEmail'
                  rules={{ required: t('contactEmailRequired') }}
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
                {t('hasLogoPermission')}
                <br></br>
                <Typography variant='caption' color='textSecondary'>
                  {t('hasLogoPermissionDetails')}
                </Typography>
              </FormLabel>
              <Controller
                control={control}
                name='hasLogoPermission'
                rules={{ required: t('common:form.required') }}
                render={({ field }) => (
                  <>
                    <Select {...field} sx={{ width: '200px' }}>
                      <MenuItem value='yes'>{t('common:form.yes')}</MenuItem>
                      <MenuItem value='no'>{t('common:form.no')}</MenuItem>
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
                {t('whatToolsCreateGtfs')}
                <br></br>
                <Typography variant='caption' color='textSecondary'>
                  {t('whatToolsCreateGtfsDetails')}
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
                {t('common:back')}
              </Button>
            </Grid>
            <Grid item>
              <Button type='submit' variant='contained' sx={{ mt: 3, mb: 2 }}>
                {t('common:form.submit')}
              </Button>
            </Grid>
          </Grid>
        </Grid>
      </form>
    </>
  );
}
