import * as React from 'react';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import { useFormik } from 'formik';
import * as Yup from 'yup';
import { getAuth } from 'firebase/auth';
import 'firebase/firestore';
import {
  Alert,
  Box,
  Checkbox,
  CssBaseline,
  FormControlLabel,
} from '@mui/material';
import { useAppDispatch } from '../hooks';
import { refreshUserInformation } from '../store/profile-reducer';
import { useNavigate } from 'react-router-dom';
import {
  selectUserProfileStatus,
  selectRegistrationError,
} from '../store/profile-selectors';
import { useSelector } from 'react-redux';
import { ACCOUNT_TARGET } from '../constants/Navigation';

export default function CompleteRegistration(): React.ReactElement {
  const auth = getAuth();
  const user = auth.currentUser;
  const dispatch = useAppDispatch();
  const navigateTo = useNavigate();

  const userProfileStatus = useSelector(selectUserProfileStatus);
  const registrationError = useSelector(selectRegistrationError);

  React.useEffect(() => {
    if (userProfileStatus === 'registered') {
      navigateTo(ACCOUNT_TARGET);
    }
  }, [userProfileStatus]);

  const CompleteRegistrationSchema = Yup.object().shape({
    fullName: Yup.string().required('Your full name is required.'),
    requiredCheck: Yup.boolean().oneOf([true], 'This field must be checked'),
    agreeToTerms: Yup.boolean()
      .required('You must accept the terms and conditions.')
      .isTrue('You must accept the terms and conditions.'),
    agreeToPrivacyPolicy: Yup.boolean()
      .required('You must agree to the privacy policy.')
      .isTrue('You must agree to the privacy policy.'),
  });

  const formik = useFormik({
    initialValues: {
      fullName: '',
      organizationName: '',
      receiveAPIAnnouncements: false,
      agreeToTerms: false,
      agreeToPrivacyPolicy: false,
    },
    validationSchema: CompleteRegistrationSchema,
    onSubmit: async (values) => {
      if (user != null) {
        dispatch(
          refreshUserInformation({
            fullName: values?.fullName,
            organization: values?.organizationName,
            isRegisteredToReceiveAPIAnnouncements:
              values?.receiveAPIAnnouncements,
          }),
        );
      }
    },
  });

  return (
    <Container component='main' maxWidth='sm'>
      <CssBaseline />
      <Box
        sx={{
          mt: 12,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Typography
          component='h1'
          variant='h5'
          color='primary'
          fontWeight='bold'
        >
          Your API Account
        </Typography>
        <Typography component='h1' variant='h6' color='primary'>
          Contact Information
        </Typography>
        <form onSubmit={formik.handleSubmit} noValidate>
          <TextField
            margin='normal'
            required
            fullWidth
            id='fullName'
            label='Full Name'
            name='fullName'
            autoFocus
            onChange={formik.handleChange}
            value={formik.values.fullName}
            error={formik.errors.fullName != null}
          />
          {formik.errors.fullName != null ? (
            <Alert severity='error'>{formik.errors.fullName}</Alert>
          ) : null}
          <TextField
            margin='normal'
            fullWidth
            id='organizationName'
            label='Organization Name'
            name='organizationName'
            onChange={formik.handleChange}
            value={formik.values.organizationName}
          />
          {user?.email !== null &&
          user?.email !== undefined &&
          user?.email !== '' ? (
            <FormControlLabel
              control={
                <Checkbox
                  id='receiveAPIAnnouncements'
                  value={formik.values.receiveAPIAnnouncements}
                  onChange={formik.handleChange}
                  color='primary'
                />
              }
              label='I would like to receive new API release announcements via email.'
              sx={{ width: '100%' }}
            />
          ) : null}
          <FormControlLabel
            control={
              <Checkbox
                id='agreeToTerms'
                required
                value={formik.values.agreeToTerms}
                onChange={formik.handleChange}
                color='primary'
              />
            }
            label='I agree to the terms and conditions'
            sx={{ width: '100%' }}
          />
          {formik.errors.agreeToTerms != null ? (
            <Alert severity='error'>{formik.errors.agreeToTerms}</Alert>
          ) : null}
          <FormControlLabel
            control={
              <Checkbox
                id='agreeToPrivacyPolicy'
                required
                value={formik.values.agreeToPrivacyPolicy}
                onChange={formik.handleChange}
                color='primary'
              />
            }
            label='I have read and agree to the privacy policy.'
            sx={{ width: '100%' }}
          />
          {formik.errors.agreeToPrivacyPolicy != null ? (
            <Alert severity='error'>{formik.errors.agreeToPrivacyPolicy}</Alert>
          ) : null}
          <Box
            width={'100%'}
            sx={{
              mt: 2,
              display: 'flex',
              justifyContent: 'center',
            }}
          >
            <Button type='submit' variant='contained'>
              Finish Account Setup
            </Button>
          </Box>
        </form>
        {registrationError !== null ? (
          <Alert severity='error' sx={{ mt: 2 }}>
            {registrationError.message}
          </Alert>
        ) : null}
      </Box>
    </Container>
  );
}
