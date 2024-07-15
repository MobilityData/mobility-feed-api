import {
  Typography,
  Grid,
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
  Button,
  MenuItem,
  Select,
  TextField,
  FormHelperText,
} from '@mui/material';
import { Controller, type SubmitHandler, useForm } from 'react-hook-form';
import { type FeedSubmissionFormFormInput } from '.';

export interface FeedSubmissionFormInputSecondStep {
  country: string;
  region: string;
  municipality: string;
  isAuthRequired: string;
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
      isAuthRequired: initialValues.isAuthRequired,
    },
  });
  const onSubmit: SubmitHandler<FeedSubmissionFormInputSecondStep> = (data) => {
    submitFormData(data);
  };

  return (
    <>
      <Typography gutterBottom>GTFS Schedule Feed</Typography>
      {/* eslint-disable-next-line @typescript-eslint/no-misused-promises */}
      <form onSubmit={handleSubmit(onSubmit)}>
        <Grid container direction={'column'} rowSpacing={2}>
          <Grid item>
            <FormControl
              component='fieldset'
              error={errors.country !== undefined}
            >
              <FormLabel component='legend' required>
                Country
              </FormLabel>
              <Controller
                rules={{ required: 'Country is required' }}
                control={control}
                name='country'
                render={({ field }) => (
                  <>
                    <Select
                      {...field}
                      value={undefined}
                      displayEmpty
                      sx={{ minWidth: '250px' }}
                    >
                      <MenuItem value={undefined}>
                        <em>Choose a country</em>
                      </MenuItem>
                      {/* TODO: country dropdown */}
                      <MenuItem value={'CA'}>Canada</MenuItem>
                      <MenuItem value={'US'}>United States</MenuItem>
                    </Select>
                    <FormHelperText>
                      {errors.country?.message ?? ''}
                    </FormHelperText>
                  </>
                )}
              />
            </FormControl>
          </Grid>
          <Grid item>
            <FormControl component='fieldset' fullWidth>
              <FormLabel component='legend'>Region</FormLabel>
              <Controller
                control={control}
                name='region'
                render={({ field }) => (
                  <TextField className='md-small-input' {...field} />
                )}
              />
            </FormControl>
          </Grid>
          <Grid item>
            <FormControl component='fieldset' fullWidth>
              <FormLabel component='legend'>Municipality</FormLabel>
              <Controller
                control={control}
                name='municipality'
                render={({ field }) => (
                  <TextField className='md-small-input' {...field} />
                )}
              />
            </FormControl>
          </Grid>
          <Grid item>
            <FormControl component='fieldset'>
              <FormLabel component='legend'>
                Is authentication required?
              </FormLabel>
              <Controller
                control={control}
                name='isAuthRequired'
                render={({ field }) => (
                  <RadioGroup {...field}>
                    <FormControlLabel
                      value='yes'
                      control={<Radio />}
                      label='Yes'
                    />
                    <FormControlLabel
                      value='no'
                      control={<Radio />}
                      label='No'
                    />
                  </RadioGroup>
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
                Back
              </Button>
            </Grid>
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
