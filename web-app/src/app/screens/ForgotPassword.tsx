import * as React from 'react';
import Button from '@mui/material/Button';
import CssBaseline from '@mui/material/CssBaseline';
import TextField from '@mui/material/TextField';
import Link from '@mui/material/Link';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
// import { useNavigate } from 'react-router-dom';
import { useAppDispatch } from '../hooks';
import { resetPassword } from '../store/profile-reducer';
import { useSelector } from 'react-redux';
import { useFormik } from 'formik';
import * as Yup from 'yup';
import { Alert } from '@mui/material';
import {
  selectResetPasswordError,
  //   selectUserProfileStatus, TODO uncomment once complete reg is merged
  selectisRecoveryEmailSent,
} from '../store/selectors';

export default function ForgotPassword(): React.ReactElement {
  const dispatch = useAppDispatch();
  //   const navigateTo = useNavigate();
  //   const userProfileStatus = useSelector(selectUserProfileStatus);
  const resetPasswordError = useSelector(selectResetPasswordError);
  const resetPasswordSuccess = useSelector(selectisRecoveryEmailSent);

  const SignInSchema = Yup.object().shape({
    email: Yup.string().email().required('Email is required'),
  });

  const formik = useFormik({
    initialValues: {
      email: '',
    },
    validationSchema: SignInSchema,
    onSubmit: (values) => {
      dispatch(resetPassword(values.email));
    },
  });

  //   React.useEffect(() => {
  //     if (userProfileStatus === 'registered') {
  //       navigateTo(ACCOUNT_TARGET);
  //     }
  //     if (userProfileStatus === 'authenticated') {
  //       navigateTo(COMPLETE_REGISTRATION_TARGET);
  //     }
  //   }, [userProfileStatus]);

  return (
    <Container component='main' maxWidth='xs'>
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
          Reset Password
        </Typography>
        <Typography component='h5'>
          Don&apos;t have an account?{' '}
          <Link href='/sign-up' color={'inherit'} fontWeight='bold'>
            Register Here
          </Link>
          .
        </Typography>
        <Box
          component='form'
          onSubmit={formik.handleSubmit}
          noValidate
          sx={{
            mt: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}
        >
          <TextField
            margin='normal'
            required
            fullWidth
            id='email'
            label='Email Address'
            name='email'
            autoComplete='email'
            autoFocus
            onChange={formik.handleChange}
            value={formik.values.email}
            error={formik.errors.email != null}
          />
          {formik.errors.email != null ? (
            <Alert severity='error' data-testid='emailError'>
              {formik.errors.email}
            </Alert>
          ) : null}

          <Button
            type='submit'
            variant='contained'
            sx={{ mt: 3, mb: 2 }}
            onClick={() => formik.handleChange}
            data-testid='signin'
          >
            Send Recovery Email
          </Button>
          {resetPasswordError != null ? (
            <Alert severity='error' data-testid='firebaseError'>
              {resetPasswordError.message}
            </Alert>
          ) : null}
          {resetPasswordSuccess ? (
            <Alert severity='success'>A recovery email was sent.</Alert>
          ) : null}
        </Box>
      </Box>
    </Container>
  );
}
