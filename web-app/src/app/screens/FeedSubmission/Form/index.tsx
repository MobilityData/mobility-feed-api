import React from 'react';
import { type SubmitHandler, useForm, Controller } from 'react-hook-form';

import {
  Button,
  FormControl,
  Input,
  Grid,
  Select,
  MenuItem,
  RadioGroup,
  FormControlLabel,
  Radio,
  FormLabel,
  Typography,
  colors,
  Checkbox,
} from '@mui/material';

export interface FeedSubmissionFormProps {
  activeStep: number;
  handleBack: () => void;
  handleNext: () => void;
}

interface FeedSubmissionFormFormInput {
  name: string;
  isOfficialProducer: string;
  dataType: string;
  transitProviderName: string;
  feedLink: string;
  licensePath: string;
  country: string;
  region: string;
  municipality: string;
  tripUpdates: boolean;
  vehiclePositions: boolean;
  serviceAlerts: boolean;
  gtfsRealtimeLink: string;
  gtfsRelatedScheduleLink: string;
  note: string;
  isAuthRequired: string;
  dataProducerEmail: string;
  isInterestedInQualityAudit: boolean;
  whatToolsUsedText: string;
}

export default function FeedSubmissionForm({
  activeStep,
  handleNext,
  handleBack,
}: FeedSubmissionFormProps): React.ReactElement {
  const { control, handleSubmit, getValues } = useForm({
    defaultValues: {
      name: '',
      isOfficialProducer: '',
      dataType: 'GTFS Schedule',
      transitProviderName: '',
      feedLink: '',
      licensePath: '',
      country: '',
      region: '',
      municipality: '',
      tripUpdates: false,
      vehiclePositions: false,
      serviceAlerts: false,
      gtfsRealtimeLink: '',
      gtfsRelatedScheduleLink: '',
      note: '',
      isAuthRequired: 'no',
      dataProducerEmail: '',
      isInterestedInQualityAudit: false,
      whatToolsUsedText: '',
    },
  });

  // const handleChange = (event): void => {
  //   const { name, value, checked } = event.target;
  // setFormData((prevData) => ({
  //     ...prevData,
  //     [name]: name === 'isOfficialProducer' ? checked : value,
  //   }));
  // };

  //   const handleSubmit = (event): void => {
  //     event.preventDefault();
  // console.log(formData);
  //     // Handle form submission here
  //   };

  const renderFirstStep = (): JSX.Element => {
    const onSubmit: SubmitHandler<FeedSubmissionFormFormInput> = (data) => {
      console.log(data);
    };
    return (
      <>
        <Typography
          sx={{
            color: colors.blue.A700,
            fontWeight: 'bold',
            fontSize: { xs: 18, sm: 24 },
          }}
        >
          Add or update a feed
        </Typography>
        {/* eslint-disable-next-line @typescript-eslint/no-misused-promises */}
        <form onSubmit={handleSubmit(onSubmit)}>
          <Grid container direction={'column'} rowSpacing={2}>
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend' required>
                  Your Name and (if applicable) Organization
                </FormLabel>
                <Controller
                  rules={{ required: true }}
                  control={control}
                  name='name'
                  render={({ field }) => <Input {...field} />}
                />
              </FormControl>
            </Grid>
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend' required>
                  Are you the official producer or transit agency responsible
                  for this data ?
                </FormLabel>
                <Controller
                  rules={{ required: true }}
                  control={control}
                  name='isOfficialProducer'
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
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend' required>
                  Data Type
                </FormLabel>
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
              <FormControl component='fieldset'>
                <FormLabel component='legend'>Transit Provider Name</FormLabel>
                <Controller
                  control={control}
                  name='transitProviderName'
                  render={({ field }) => <Input {...field} />}
                />
              </FormControl>
            </Grid>
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend' required>
                  Feed link
                </FormLabel>
                <Controller
                  rules={{ required: true }}
                  control={control}
                  name='feedLink'
                  render={({ field }) => <Input {...field} />}
                />
              </FormControl>
            </Grid>
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend'>Link to feed license</FormLabel>
                <Controller
                  control={control}
                  name='licensePath'
                  render={({ field }) => <Input {...field} />}
                />
              </FormControl>
            </Grid>

            <Grid container spacing={2}>
              <Grid item>
                <Button
                  onClick={handleBack}
                  variant='outlined'
                  sx={{ mt: 3, mb: 2 }}
                >
                  Back
                </Button>
              </Grid>
              <Grid item>
                <Button
                  onClick={handleNext}
                  variant='contained'
                  sx={{ mt: 3, mb: 2 }}
                >
                  Next
                </Button>
              </Grid>
            </Grid>
          </Grid>
        </form>
      </>
    );
  };
  const renderSecondStepGTFS = (): JSX.Element => {
    const onSubmit: SubmitHandler<FeedSubmissionFormFormInput> = (data) => {
      console.log(data);
    };
    return (
      <>
        <Typography
          sx={{
            color: colors.blue.A700,
            fontWeight: 'bold',
            fontSize: { xs: 18, sm: 24 },
          }}
        >
          Add or update a feed
        </Typography>
        <Typography gutterBottom>GTFS Schedule Feed</Typography>
        {/* eslint-disable-next-line @typescript-eslint/no-misused-promises */}
        <form onSubmit={handleSubmit(onSubmit)}>
          <Grid container direction={'column'} rowSpacing={2}>
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend' required>
                  Country
                </FormLabel>
                <Controller
                  rules={{ required: true }}
                  control={control}
                  name='country'
                  render={({ field }) => <Input {...field} />}
                />
              </FormControl>
            </Grid>
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend'>Region</FormLabel>
                <Controller
                  control={control}
                  name='region'
                  render={({ field }) => <Input {...field} />}
                />
              </FormControl>
            </Grid>
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend'>Municipality</FormLabel>
                <Controller
                  control={control}
                  name='municipality'
                  render={({ field }) => <Input {...field} />}
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
                  onClick={handleBack}
                  variant='outlined'
                  sx={{ mt: 3, mb: 2 }}
                >
                  Back
                </Button>
              </Grid>
              <Grid item>
                <Button
                  onClick={handleNext}
                  variant='contained'
                  sx={{ mt: 3, mb: 2 }}
                >
                  Next
                </Button>
              </Grid>
            </Grid>
          </Grid>
        </form>
      </>
    );
  };
  const renderSecondStepGTFSRT = (): JSX.Element => {
    const onSubmit: SubmitHandler<FeedSubmissionFormFormInput> = (data) => {
      console.log(data);
    };

    const entityTypeCheckBoxLabels = {
      tripUpdates: 'Trip Updates',
      vehiclePositions: 'Vehicle Positions',
      serviceAlerts: 'Service Alerts',
    };

    return (
      <>
        <Typography
          sx={{
            color: colors.blue.A700,
            fontWeight: 'bold',
            fontSize: { xs: 18, sm: 24 },
          }}
        >
          Add or update a feed
        </Typography>
        <Typography
          sx={{
            fontSize: { xs: 12, sm: 18 },
          }}
        >
          GTFS Realtime Feed
        </Typography>
        {/* eslint-disable-next-line @typescript-eslint/no-misused-promises */}
        <form onSubmit={handleSubmit(onSubmit)}>
          <Grid container direction={'column'} rowSpacing={2}>
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend' required>
                  Entity Type
                </FormLabel>
                {(
                  ['tripUpdates', 'vehiclePositions', 'serviceAlerts'] as const
                ).map((entityType) => (
                  <Controller
                    key={entityType}
                    rules={{ required: true }}
                    control={control}
                    name={entityType}
                    render={({ field }) => {
                      console.log(field);
                      return (
                        <FormControlLabel
                          control={<Checkbox />}
                          label={entityTypeCheckBoxLabels[entityType]}
                        />
                      );
                    }}
                  />
                ))}
              </FormControl>
            </Grid>
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend'>
                  GTFS Realtime feed link
                </FormLabel>
                <Controller
                  control={control}
                  name='gtfsRealtimeLink'
                  render={({ field }) => <Input {...field} />}
                />
              </FormControl>
            </Grid>
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend'>
                  Link to related GTFS Schedule feed
                </FormLabel>
                <Controller
                  control={control}
                  name='gtfsRelatedScheduleLink'
                  render={({ field }) => <Input {...field} />}
                />
              </FormControl>
            </Grid>
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend'>
                  Note
                  <br />
                  e.g “Aggregate” or “only contains Trip Updates and Vehicle
                  Positions”
                </FormLabel>
                <Controller
                  control={control}
                  name='note'
                  render={({ field }) => <Input {...field} />}
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
                  onClick={handleBack}
                  variant='outlined'
                  sx={{ mt: 3, mb: 2 }}
                >
                  Back
                </Button>
              </Grid>
              <Grid item>
                <Button
                  onClick={handleNext}
                  variant='contained'
                  sx={{ mt: 3, mb: 2 }}
                >
                  Next
                </Button>
              </Grid>
            </Grid>
          </Grid>
        </form>
      </>
    );
  };
  const renderThirdStep = (): JSX.Element => {
    const onSubmit: SubmitHandler<FeedSubmissionFormFormInput> = (data) => {
      console.log(data);
    };
    return (
      <>
        <Typography
          sx={{
            color: colors.blue.A700,
            fontWeight: 'bold',
            fontSize: { xs: 18, sm: 24 },
          }}
        >
          Add or update a feed
        </Typography>
        {/* eslint-disable-next-line @typescript-eslint/no-misused-promises */}
        <form onSubmit={handleSubmit(onSubmit)}>
          <Grid container direction={'column'} rowSpacing={2}>
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend' required>
                  Data Producer Email
                  <Typography sx={{ fontSize: 12 }} gutterBottom>
                    This is an official email that consumers of the feed can
                    contact to ask questions.
                  </Typography>
                </FormLabel>
                <Controller
                  rules={{ required: true }}
                  control={control}
                  name='dataProducerEmail'
                  render={({ field }) => <Input {...field} />}
                />
              </FormControl>
            </Grid>
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend'>
                  Are you interested in a data quality audit?
                  <Typography sx={{ fontSize: 12 }} gutterBottom>
                    This is a 1 time meeting with MobilityData to review your
                    GTFS validation report and discuss possible improvements.
                  </Typography>
                </FormLabel>
                <Controller
                  control={control}
                  name='isInterestedInQualityAudit'
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
            <Grid item>
              <FormControl component='fieldset'>
                <FormLabel component='legend'>
                  What tools do you use to create GTFS data? Could include open
                  source libraries, vendor services, or other applications.
                </FormLabel>
                <Controller
                  rules={{ required: true }}
                  control={control}
                  name='whatToolsUsedText'
                  render={({ field }) => <Input {...field} />}
                />
              </FormControl>
            </Grid>

            <Grid container spacing={2}>
              <Grid item>
                <Button
                  onClick={handleBack}
                  variant='outlined'
                  sx={{ mt: 3, mb: 2 }}
                >
                  Back
                </Button>
              </Grid>
              <Grid item>
                <Button
                  onClick={handleNext}
                  variant='contained'
                  sx={{ mt: 3, mb: 2 }}
                >
                  Next
                </Button>
              </Grid>
            </Grid>
          </Grid>
        </form>
      </>
    );
  };

  return (
    <>
      {activeStep === 0 && renderFirstStep()}
      {activeStep === 1 &&
        getValues('dataType') === 'GTFS Schedule' &&
        renderSecondStepGTFS()}
      {activeStep === 1 &&
        getValues('dataType') === 'GTFS Realtime' &&
        renderSecondStepGTFSRT()}
      {activeStep === 2 && renderThirdStep()}
    </>
  );
}
