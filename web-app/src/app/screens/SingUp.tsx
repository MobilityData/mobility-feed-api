import * as React from 'react';
import Button from '@mui/material/Button';
import CssBaseline from '@mui/material/CssBaseline';
import TextField from '@mui/material/TextField';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import Link from '@mui/material/Link';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import GoogleIcon from '@mui/icons-material/Google';
import GitHubIcon from '@mui/icons-material/GitHub';
import { useNavigate } from 'react-router-dom';
import * as Yup from 'yup';
import { useFormik } from 'formik';
import { useAppDispatch } from '../hooks';
import { loginFail, loginWithProvider, signUp } from '../store/profile-reducer';
import { Alert } from '@mui/material';
import { useSelector } from 'react-redux';
import {
  ACCOUNT_TARGET,
  COMPLETE_REGISTRATION_TARGET,
  SIGN_IN_TARGET,
} from '../constants/Navigation';
import '../styles/SignUp.css';
import { selectSignUpError, selectUserProfileStatus } from '../store/selectors';
import {
  ErrorSource,
  OauthProvider,
  oathProviders,
  passwordValidatioError,
} from '../types';
import { type UserCredential, getAuth, signInWithPopup } from 'firebase/auth';
import ReCAPTCHA from 'react-google-recaptcha';
import { getEnvConfig } from '../utils/config';

export default function SignUp(): React.ReactElement {
  const navigateTo = useNavigate();
  const dispatch = useAppDispatch();
  const signUpError = useSelector(selectSignUpError);
  const userProfileStatus = useSelector(selectUserProfileStatus);
  const SignUpSchema = Yup.object().shape({
    email: Yup.string().email().required('Email is required'),
    confirmEmail: Yup.string().oneOf(
      [Yup.ref('email'), ''],
      'Emails do not match',
    ),
    password: Yup.string()
      .required('Password is required')
      .matches(
        /^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[^$*.[\]{}()?"!@#%&/\\,><':;|_~`])(?=.{12,})/,
        passwordValidatioError,
      ),
    confirmPassword: Yup.string().oneOf(
      [Yup.ref('password'), ''],
      'Passwords do not match',
    ),
    agreeToTerms: Yup.boolean()
      .required('You must accept the terms and conditions.')
      .isTrue('You must accept the terms and conditions.'),
    reCaptcha: Yup.string().required('You must verify you are not a robot.'),
  });

  const formik = useFormik({
    initialValues: {
      email: '',
      confirmEmail: '',
      password: '',
      confirmPassword: '',
      agreeToTerms: false,
      reCaptcha: null,
    },
    validationSchema: SignUpSchema,
    onSubmit: (values) => {
      dispatch(
        signUp({
          email: values.email,
          password: values.password,
          redirectScreen: ACCOUNT_TARGET,
          navigateTo,
        }),
      );
    },
  });

  React.useEffect(() => {
    if (userProfileStatus === 'registered') {
      navigateTo(ACCOUNT_TARGET);
    }
    if (userProfileStatus === 'authenticated') {
      navigateTo(COMPLETE_REGISTRATION_TARGET);
    }
  }, [userProfileStatus]);

  const signInWithProvider = (oauthProvider: OauthProvider): void => {
    const auth = getAuth();
    const provider = oathProviders[oauthProvider];
    signInWithPopup(auth, provider)
      .then((userCredential: UserCredential) => {
        dispatch(loginWithProvider({ oauthProvider, userCredential }));
      })
      .catch((error) => {
        dispatch(
          loginFail({
            code: error.code,
            message: error.message,
            source: ErrorSource.Login,
          }),
        );
      });
  };

  const onChangeReCaptcha = (value: string | null): void => {
    void formik.setFieldValue('reCaptcha', value);
  };

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
          API Sign Up
        </Typography>
        <Typography component='h5'>
          Already have an account?{' '}
          <Link href={SIGN_IN_TARGET} color={'inherit'} fontWeight='bold'>
            Log In Here
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
            <Alert severity='error'>{formik.errors.email}</Alert>
          ) : null}
          <TextField
            margin='normal'
            required
            fullWidth
            id='confirmEmail'
            label='Confirm Email'
            name='confirmEmail'
            autoComplete='email'
            autoFocus
            onChange={formik.handleChange}
            value={formik.values.confirmEmail}
            error={formik.errors.confirmEmail != null}
          />
          {formik.errors.confirmEmail != null ? (
            <Alert severity='error'>{formik.errors.confirmEmail}</Alert>
          ) : null}
          <TextField
            margin='normal'
            required
            fullWidth
            name='password'
            label='Password'
            type='password'
            id='password'
            autoComplete='current-password'
            onChange={formik.handleChange}
            value={formik.values.password}
            error={formik.errors.password != null}
          />
          {formik.errors.password != null ? (
            <Alert severity='error' data-testid='passwordError'>
              {formik.errors.password}
            </Alert>
          ) : null}
          <TextField
            margin='normal'
            required
            fullWidth
            name='confirmPassword'
            label='Confirm Password'
            type='password'
            id='confirmPassword'
            autoComplete='new-password'
            onChange={formik.handleChange}
            value={formik.values.confirmPassword}
            error={formik.errors.confirmPassword != null}
          />
          {formik.errors.confirmPassword != null ? (
            <Alert severity='error' data-testid='confirmPasswordError'>
              {formik.errors.confirmPassword}
            </Alert>
          ) : null}
          <FormControlLabel
            control={
              <Checkbox
                id='agreeToTerms'
                value={formik.values.agreeToTerms}
                onChange={formik.handleChange}
                color='primary'
              />
            }
            label='I agree to the terms and conditions'
            sx={{ width: '100%' }}
          />
          {formik.errors.agreeToTerms != null ? (
            <Alert severity='error' data-testid='agreeToTermsError'>
              {formik.errors.agreeToTerms}
            </Alert>
          ) : null}
          <Box m={1}>
            <ReCAPTCHA
              sitekey={getEnvConfig('REACT_APP_RECAPTCHA_SITE_KEY')}
              onChange={onChangeReCaptcha}
              data-testid='reCaptcha'
              style={{ alignSelf: 'center', margin: 'normal' }}
            />
          </Box>
          {formik.errors.reCaptcha != null ? (
            <Alert severity='error' data-testid='reCaptchaError'>
              {formik.errors.reCaptcha}
            </Alert>
          ) : null}
          <Button
            type='submit'
            variant='contained'
            sx={{ mt: 3, mb: 2, alignSelf: 'center' }}
            onClick={formik.handleChange}
            id='sign-up-button'
          >
            Sign Up
          </Button>
          {signUpError != null ? (
            <Alert severity='error'>{signUpError.message}</Alert>
          ) : null}
        </Box>
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            mb: 1,
          }}
        >
          <p className='hr-text'>
            <span>OR</span>
          </p>
        </Box>

        <Button
          variant='outlined'
          color='primary'
          sx={{ mb: 2 }}
          startIcon={<GoogleIcon />}
          className='sso-button'
          onClick={() => {
            signInWithProvider(OauthProvider.Google);
          }}
        >
          Sign Up With Google
        </Button>
        <Button
          variant='outlined'
          color='primary'
          sx={{ mb: 2 }}
          startIcon={<GitHubIcon />}
          className='sso-button'
          onClick={() => {
            signInWithProvider(OauthProvider.Github);
          }}
        >
          Sign Up With GitHub
        </Button>
      </Box>
    </Container>
  );
}
