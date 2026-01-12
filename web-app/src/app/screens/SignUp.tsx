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
import AppleIcon from '@mui/icons-material/Apple';
import { useSearchParams, useNavigate } from 'react-router-dom';
import * as Yup from 'yup';
import { useFormik } from 'formik';
import { useAppDispatch } from '../hooks';
import {
  loginWithProvider,
  signUp,
  signUpFail,
  verifyEmail,
} from '../store/profile-reducer';
import {
  Alert,
  IconButton,
  InputAdornment,
  Snackbar,
  Tooltip,
} from '@mui/material';
import { useSelector } from 'react-redux';
import {
  ACCOUNT_TARGET,
  ADD_FEED_TARGET,
  COMPLETE_REGISTRATION_TARGET,
  POST_REGISTRATION_TARGET,
  SIGN_IN_TARGET,
} from '../constants/Navigation';
import { selectSignUpError, selectUserProfileStatus } from '../store/selectors';
import { ProfileErrorSource, OauthProvider, oathProviders } from '../types';
import {
  passwordValidationError,
  passwordValidationRegex,
} from '../constants/Validation';
import { type UserCredential, getAuth, signInWithPopup } from 'firebase/auth';
import ReCAPTCHA from 'react-google-recaptcha';
import { getEnvConfig } from '../utils/config';
import { VisibilityOffOutlined, VisibilityOutlined } from '@mui/icons-material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';

export default function SignUp(): React.ReactElement {
  const [showPassword, setShowPassword] = React.useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = React.useState(false);
  const [showNoEmailSnackbar, setShowNoEmailSnackbar] = React.useState(false);
  const [searchParams] = useSearchParams();

  const navigateTo = useNavigate();
  const dispatch = useAppDispatch();
  const signUpError = useSelector(selectSignUpError);
  const userProfileStatus = useSelector(selectUserProfileStatus);
  const [isSubmitted, setIsSubmitted] = React.useState(false);

  const SignUpSchema = Yup.object().shape({
    email: Yup.string()
      .email('Email format is invalid.')
      .required('Email is required'),
    confirmEmail: Yup.string().oneOf(
      [Yup.ref('email'), ''],
      'Emails do not match',
    ),
    password: Yup.string()
      .required('Password is required')
      .matches(passwordValidationRegex, 'Password error'),
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
    validateOnChange: isSubmitted,
    validateOnBlur: true,
    onSubmit: (values) => {
      dispatch(
        signUp({
          email: values.email,
          password: values.password,
        }),
      );
    },
  });

  React.useEffect(() => {
    if (userProfileStatus === 'registered') {
      if (searchParams.has('add_feed')) {
        navigateTo(ADD_FEED_TARGET, { state: { from: 'registration' } });
      } else {
        navigateTo(ACCOUNT_TARGET);
      }
    }
    if (userProfileStatus === 'authenticated') {
      navigateTo(COMPLETE_REGISTRATION_TARGET + '?' + searchParams.toString());
    }
    if (userProfileStatus === 'unverified') {
      navigateTo(POST_REGISTRATION_TARGET + '?' + searchParams.toString());
    }
  }, [userProfileStatus]);

  const signInWithProvider = (oauthProvider: OauthProvider): void => {
    const auth = getAuth();
    const provider = oathProviders[oauthProvider];
    signInWithPopup(auth, provider)
      .then((userCredential: UserCredential) => {
        if (!userCredential.user.emailVerified) {
          dispatch(verifyEmail());
        }
        if (userCredential.user.email == null) {
          setShowNoEmailSnackbar(true);
        } else {
          dispatch(loginWithProvider({ oauthProvider, userCredential }));
        }
      })
      .catch((error) => {
        dispatch(
          signUpFail({
            code: error.code,
            message: error.message,
            source: ProfileErrorSource.Login,
          }),
        );
      });
  };

  const termsAndConditionsElement = (
    <span>
      I have read and I agree to the
      <Button
        variant='text'
        className='inline'
        href={'/terms-and-conditions'}
        rel='noreferrer'
        target='_blank'
        endIcon={<OpenInNewIcon />}
      >
        terms and conditions
      </Button>
      .
    </span>
  );

  const onChangeReCaptcha = (value: string | null): void => {
    void formik.setFieldValue('reCaptcha', value);
  };

  return (
    <Container component='main' maxWidth='xs'>
      <Snackbar
        open={showNoEmailSnackbar}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        onClose={() => {
          setShowNoEmailSnackbar(false);
        }}
      >
        <Alert
          severity='error'
          onClose={() => {
            setShowNoEmailSnackbar(false);
          }}
        >
          No public email provided in Github account. Please use a different
          registration method.
        </Alert>
      </Snackbar>
      <CssBaseline />
      <Box
        sx={{
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
          <Link
            href={`${SIGN_IN_TARGET}?${searchParams.toString()}`}
            color={'inherit'}
            fontWeight='bold'
          >
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
            type={showPassword ? 'text' : 'password'}
            id='password'
            autoComplete='current-password'
            onChange={formik.handleChange}
            value={formik.values.password}
            error={formik.errors.password != null}
            InputProps={{
              endAdornment: (
                <InputAdornment position='end'>
                  <Tooltip title='Toggle Password Visibility'>
                    <IconButton
                      color='primary'
                      aria-label='toggle password visibility'
                      onClick={() => {
                        setShowPassword(!showPassword);
                      }}
                    >
                      {showPassword ? (
                        <VisibilityOutlined fontSize='small' />
                      ) : (
                        <VisibilityOffOutlined fontSize='small' />
                      )}
                    </IconButton>
                  </Tooltip>
                </InputAdornment>
              ),
            }}
          />
          {formik.errors.password != null ? (
            <Alert severity='error' data-testid='passwordError'>
              {passwordValidationError}
            </Alert>
          ) : null}
          <TextField
            margin='normal'
            required
            fullWidth
            name='confirmPassword'
            label='Confirm Password'
            type={showConfirmPassword ? 'text' : 'password'}
            id='confirmPassword'
            autoComplete='new-password'
            onChange={formik.handleChange}
            value={formik.values.confirmPassword}
            error={formik.errors.confirmPassword != null}
            InputProps={{
              endAdornment: (
                <InputAdornment position='end'>
                  <Tooltip title='Toggle Password Visibility'>
                    <IconButton
                      color='primary'
                      aria-label='toggle Password visibility'
                      onClick={() => {
                        setShowConfirmPassword(!showConfirmPassword);
                      }}
                    >
                      {showConfirmPassword ? (
                        <VisibilityOutlined fontSize='small' />
                      ) : (
                        <VisibilityOffOutlined fontSize='small' />
                      )}
                    </IconButton>
                  </Tooltip>
                </InputAdornment>
              ),
            }}
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
            label={termsAndConditionsElement}
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
            disabled={!formik.values.agreeToTerms}
            sx={{ mt: 3, mb: 2, alignSelf: 'center' }}
            onClick={() => {
              setIsSubmitted(true);
            }}
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
          onClick={() => {
            signInWithProvider(OauthProvider.Github);
          }}
        >
          Sign Up With GitHub
        </Button>
        <Button
          variant='outlined'
          color='primary'
          sx={{ mb: 2 }}
          startIcon={<AppleIcon />}
          onClick={() => {
            signInWithProvider(OauthProvider.Apple);
          }}
        >
          Sign Up With Apple
        </Button>
      </Box>
    </Container>
  );
}
