import * as React from 'react';
import Button from '@mui/material/Button';
import CssBaseline from '@mui/material/CssBaseline';
import TextField from '@mui/material/TextField';
import Link from '@mui/material/Link';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import GoogleIcon from '@mui/icons-material/Google';
import GitHubIcon from '@mui/icons-material/GitHub';
import AppleIcon from '@mui/icons-material/Apple';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAppDispatch } from '../hooks';
import { useRemoteConfig } from '../context/RemoteConfigProvider';
import { login, loginFail, loginWithProvider } from '../store/profile-reducer';
import {
  OauthProvider,
  type EmailLogin,
  ProfileErrorSource,
  oathProviders,
} from '../types';
import { useSelector } from 'react-redux';
import { useFormik } from 'formik';
import * as Yup from 'yup';
import {
  Alert,
  IconButton,
  InputAdornment,
  Snackbar,
  Tooltip,
} from '@mui/material';
import '../styles/SignUp.css';
import {
  selectEmailLoginError,
  selectUserProfileStatus,
} from '../store/selectors';
import { getAuth, signInWithPopup, type UserCredential } from 'firebase/auth';
import {
  ACCOUNT_TARGET,
  ADD_FEED_TARGET,
  COMPLETE_REGISTRATION_TARGET,
  POST_REGISTRATION_TARGET,
} from '../constants/Navigation';
import { VisibilityOffOutlined, VisibilityOutlined } from '@mui/icons-material';
import { useEffect } from 'react';

export default function SignIn(): React.ReactElement {
  const dispatch = useAppDispatch();
  const navigateTo = useNavigate();
  const userProfileStatus = useSelector(selectUserProfileStatus);
  const emailLoginError = useSelector(selectEmailLoginError);
  const [isSubmitted, setIsSubmitted] = React.useState(false);
  const [showPassword, setShowPassword] = React.useState(false);
  const [showNoEmailSnackbar, setShowNoEmailSnackbar] = React.useState(false);
  const [enableAppleSSO, setEnableAppleSSO] = React.useState(false);
  const [searchParams] = useSearchParams();
  const { config } = useRemoteConfig();

  useEffect(() => {
    setEnableAppleSSO(config.enableAppleSSO as boolean);
  });
  const SignInSchema = Yup.object().shape({
    email: Yup.string()
      .email('Email format is invalid.')
      .required('Email is required'),

    password: Yup.string()
      .required('Password is required')
      .min(
        12,
        'Password is too short. Your password should be 12 characters minimum',
      ),
  });

  const formik = useFormik({
    initialValues: {
      email: '',
      password: '',
    },
    validationSchema: SignInSchema,
    validateOnChange: isSubmitted,
    validateOnBlur: true,
    onSubmit: (values) => {
      const emailLogin: EmailLogin = {
        email: values.email,
        password: values.password,
      };
      dispatch(login(emailLogin));
    },
  });

  React.useEffect(() => {
    if (userProfileStatus === 'registered') {
      if(searchParams.has('add_feed')) {
        navigateTo(ADD_FEED_TARGET, {state: {from: 'registration'}});
      } else {
        navigateTo(ACCOUNT_TARGET);
      }
    }
    if (userProfileStatus === 'authenticated') {
      navigateTo(COMPLETE_REGISTRATION_TARGET+"?"+searchParams.toString());
    }
    if (userProfileStatus === 'unverified') {
      navigateTo(POST_REGISTRATION_TARGET+"?"+searchParams.toString());
    }
  }, [userProfileStatus]);

  const signInWithProvider = (oauthProvider: OauthProvider): void => {
    const auth = getAuth();
    const provider = oathProviders[oauthProvider];
    signInWithPopup(auth, provider)
      .then((userCredential: UserCredential) => {
        if (userCredential.user.email == null) {
          setShowNoEmailSnackbar(true);
        } else {
          dispatch(loginWithProvider({ oauthProvider, userCredential }));
        }
      })
      .catch((error) => {
        dispatch(
          loginFail({
            code: error.code,
            message: error.message,
            source: ProfileErrorSource.Login,
          }),
        );
      });
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
          login method.
        </Alert>
      </Snackbar>
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
          API Login
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
            <Alert severity='error'>{formik.errors.email}</Alert>
          ) : null}
          <TextField
            margin='normal'
            required
            fullWidth
            name='password'
            label='Password'
            type={showPassword ? 'text' : 'password'}
            id='password'
            autoComplete='new-password'
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
            <Alert severity='error'>{formik.errors.password}</Alert>
          ) : null}
          {/* TODO: Add remember me functionality
            <FormControlLabel
            control={<Checkbox value='remember' color='primary' />}
            label='Remember me'
            sx={{ width: '100%' }}
          /> */}
          <Typography component='h5' sx={{ textAlign: 'left', width: '100%' }}>
            Forgot your password?{' '}
            <Link href='/forgot-password' color={'inherit'} fontWeight='bold'>
              Reset Here
            </Link>
            .
          </Typography>
          <Button
            type='submit'
            variant='contained'
            sx={{ mt: 3, mb: 2 }}
            onClick={() => {
              setIsSubmitted(true);
            }}
            data-testid='signin'
          >
            Sign In
          </Button>
          {emailLoginError != null ? (
            <Alert severity='error'>{emailLoginError.message}</Alert>
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
          className='sso-button'
          sx={{ mb: 2 }}
          startIcon={<GoogleIcon />}
          onClick={() => {
            signInWithProvider(OauthProvider.Google);
          }}
        >
          Sign In With Google
        </Button>
        <Button
          variant='outlined'
          color='primary'
          className='sso-button'
          sx={{ mb: 2 }}
          startIcon={<GitHubIcon />}
          onClick={() => {
            signInWithProvider(OauthProvider.Github);
          }}
        >
          Sign In With Github
        </Button>
        {enableAppleSSO && (
          <Button
            variant='outlined'
            color='primary'
            sx={{ mb: 2 }}
            startIcon={<AppleIcon />}
            className='sso-button'
            onClick={() => {
              signInWithProvider(OauthProvider.Apple);
            }}
          >
            Sign in With Apple
          </Button>
        )}
      </Box>
    </Container>
  );
}
