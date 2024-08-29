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

export interface FeedSubmissionFormFormInputFirstStep {
  isOfficialProducer: YesNoFormInput;
  dataType: string;
  transitProviderName?: string;
  feedLink?: string;
  oldFeedLink?: string;
  isUpdatingFeed: YesNoFormInput;
}

interface FormFirstStepProps {
  initialValues: FeedSubmissionFormFormInput;
  submitFormData: (formData: Partial<FeedSubmissionFormFormInput>) => void;
  setNumberOfSteps: (numberOfSteps: YesNoFormInput) => void;
}

export default function FormFirstStep({
  initialValues,
  submitFormData,
  setNumberOfSteps,
}: FormFirstStepProps): React.ReactElement {
  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<FeedSubmissionFormFormInputFirstStep>({
    defaultValues: {
      isOfficialProducer: initialValues.isOfficialProducer,
      dataType: initialValues.dataType,
      transitProviderName: initialValues.transitProviderName,
      feedLink: initialValues.feedLink,
      oldFeedLink: initialValues.oldFeedLink,
      isUpdatingFeed: initialValues.isUpdatingFeed,
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
              <FormLabel required>
                Are you the official producer or transit agency responsible for
                this data ?
              </FormLabel>
              <Controller
                rules={{ required: 'This field is required' }}
                control={control}
                name='isOfficialProducer'
                render={({ field }) => (
                  <>
                    <RadioGroup {...field}>
                      <FormControlLabel
                        value='yes'
                        control={<Radio color='default' />}
                        label='Yes'
                      />
                      <FormControlLabel
                        value='no'
                        control={<Radio sx={{}} />}
                        label='No'
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
          <Grid item>
            <FormControl
              component='fieldset'
              error={errors.dataType !== undefined}
            >
              <FormLabel required>Data Type</FormLabel>
              <Controller
                rules={{ required: 'Data type required' }}
                control={control}
                name='dataType'
                render={({ field }) => (
                  <Select {...field}>
                    <MenuItem value={'gtfs'}>GTFS Schedule</MenuItem>
                    <MenuItem value={'gtfs_rt'}>GTFS Realtime</MenuItem>
                  </Select>
                )}
              />
            </FormControl>
          </Grid>
          <Grid item>
            <FormControl component='fieldset' fullWidth>
              <FormLabel>Transit Provider Name</FormLabel>
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
                <FormLabel component='legend' required>
                  Feed link
                </FormLabel>
                <Controller
                  rules={
                    dataType === 'gtfs'
                      ? { required: 'Feed link required' }
                      : {}
                  }
                  control={control}
                  name='feedLink'
                  render={({ field }) => (
                    <TextField
                      className='md-small-input'
                      helperText={errors.feedLink?.message ?? ''}
                      error={errors.feedLink !== undefined}
                      {...field}
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
              <FormLabel required>Are you updating a feed?</FormLabel>
              <Controller
                rules={{ required: 'Field required' }}
                control={control}
                name='isUpdatingFeed'
                render={({ field }) => (
                  <Select {...field} sx={{ width: '200px' }}>
                    <MenuItem value={'yes'}>Yes</MenuItem>
                    <MenuItem value={'no'}>No</MenuItem>
                  </Select>
                )}
              />
            </FormControl>
          </Grid>
          {isUpdatingFeed === 'yes' && dataType === 'gtfs' && (
            <Grid item>
              <FormControl
                component='fieldset'
                fullWidth
                error={errors.oldFeedLink !== undefined}
              >
                <FormLabel component='legend' required>
                  Old Feed link
                </FormLabel>
                <Controller
                  rules={
                    isUpdatingFeed === 'yes' && dataType === 'gtfs'
                      ? { required: 'Old feed link required' }
                      : {}
                  }
                  control={control}
                  name='oldFeedLink'
                  render={({ field }) => (
                    <TextField
                      className='md-small-input'
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
