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

import { type SubmitHandler, Controller, useForm } from 'react-hook-form';
import { type FeedSubmissionFormFormInput } from '.';

export interface FeedSubmissionFormFormInputFirstStep {
  name: string;
  isOfficialProducer: string;
  dataType: string;
  transitProviderName: string;
  feedLink: string;
  licensePath: string;
}

interface FormFirstStepProps {
  initialValues: FeedSubmissionFormFormInput;
  submitFormData: (formData: Partial<FeedSubmissionFormFormInput>) => void;
}

export default function FormFirstStep({
  initialValues,
  submitFormData,
}: FormFirstStepProps): React.ReactElement {
  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<FeedSubmissionFormFormInputFirstStep>({
    defaultValues: {
      name: initialValues.name,
      isOfficialProducer: initialValues.isOfficialProducer,
      dataType: initialValues.dataType,
      transitProviderName: initialValues.transitProviderName,
      feedLink: initialValues.feedLink,
      licensePath: initialValues.licensePath,
    },
  });
  const onSubmit: SubmitHandler<FeedSubmissionFormFormInputFirstStep> = (
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
              error={errors.name !== undefined}
            >
              <FormLabel required>
                Your Name and (if applicable) Organization
              </FormLabel>
              <Controller
                rules={{ required: 'Your name is required' }}
                control={control}
                name='name'
                render={({ field }) => (
                  <TextField
                    {...field}
                    className='md-small-input'
                    sx={{
                      input: { py: 1 },
                    }}
                    error={errors.name !== undefined}
                    helperText={errors.name?.message ?? ''}
                  />
                )}
              />
            </FormControl>
          </Grid>
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
                rules={{ required: true }}
                control={control}
                name='dataType'
                render={({ field }) => (
                  <Select {...field}>
                    <MenuItem value={'GTFS Schedule'}>GTFS Schedule</MenuItem>
                    <MenuItem value={'GTFS Realtime'}>GTFS Realtime</MenuItem>
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
                rules={{ required: 'Feed link required' }}
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
          <Grid item>
            <FormControl component='fieldset' fullWidth>
              <FormLabel component='legend'>Link to feed license</FormLabel>
              <Controller
                control={control}
                name='licensePath'
                render={({ field }) => (
                  <TextField className='md-small-input' {...field} />
                )}
              />
            </FormControl>
          </Grid>

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
