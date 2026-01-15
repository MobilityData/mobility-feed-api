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
import { type YesNoFormInput, type FeedSubmissionFormFormInput } from '.';
import { useTranslations } from 'next-intl';
import FormLabelDescription from './components/FormLabelDescription';

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
  const t = useTranslations('feeds');
  const tCommon = useTranslations('common');
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
          <Grid>
            <FormControl component='fieldset' fullWidth>
              <FormLabel component='legend' data-cy='dataProducerEmailLabel'>
                {t('dataProducerEmail')}
              </FormLabel>
              <FormLabelDescription>
                {t('dataProducerEmailDetails')}
              </FormLabelDescription>
              <Controller
                control={control}
                name='dataProducerEmail'
                render={({ field }) => (
                  <TextField
                    className='md-small-input'
                    {...field}
                    data-cy='dataProducerEmail'
                  />
                )}
              />
            </FormControl>
          </Grid>
          <Grid>
            <FormControl
              component='fieldset'
              error={errors.isInterestedInQualityAudit !== undefined}
            >
              <FormLabel required data-cy='dataAuditLabel'>
                {t('interestedInDataAudit')}
              </FormLabel>
              <FormLabelDescription>
                {t('interestedInDataAuditDetails')}
              </FormLabelDescription>
              <Controller
                control={control}
                name='isInterestedInQualityAudit'
                rules={{ required: tCommon('form.required') }}
                render={({ field }) => (
                  <>
                    <Select
                      {...field}
                      sx={{ width: '200px' }}
                      data-cy='interestedInAudit'
                    >
                      <MenuItem value='yes'>{tCommon('form.yes')}</MenuItem>
                      <MenuItem value='no'>{tCommon('form.no')}</MenuItem>
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
            <Grid>
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
          <Grid>
            <FormControl
              component='fieldset'
              error={errors.hasLogoPermission !== undefined}
            >
              <FormLabel required data-cy='logoPermissionLabel'>
                {t('hasLogoPermission')}
              </FormLabel>
              <FormLabelDescription>
                {t('hasLogoPermissionDetails')}
              </FormLabelDescription>

              <Controller
                control={control}
                name='hasLogoPermission'
                rules={{ required: tCommon('form.required') }}
                render={({ field }) => (
                  <>
                    <Select
                      {...field}
                      sx={{ width: '200px' }}
                      data-cy='logoPermission'
                    >
                      <MenuItem value='yes'>{tCommon('form.yes')}</MenuItem>
                      <MenuItem value='no'>{tCommon('form.no')}</MenuItem>
                    </Select>
                    <FormHelperText>
                      {errors.hasLogoPermission?.message ?? ''}
                    </FormHelperText>
                  </>
                )}
              />
            </FormControl>
          </Grid>
          <Grid>
            <FormControl component='fieldset' fullWidth>
              <FormLabel>{t('whatToolsCreateGtfs')}</FormLabel>
              <FormLabelDescription>
                {t('whatToolsCreateGtfsDetails')}
              </FormLabelDescription>
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
                data-cy='fourthStepSubmit'
              >
                {tCommon('form.submit')}
              </Button>
            </Grid>
          </Grid>
        </Grid>
      </form>
    </>
  );
}
