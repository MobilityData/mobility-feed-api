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
import { useNavigate } from 'react-router-dom';
import { useAppDispatch } from '../hooks';
import { login, loginFail, loginWithProvider } from '../store/profile-reducer';
import {
  OauthProvider,
  type EmailLogin,
  ErrorSource,
  oathProviders,
} from '../types';
import { useSelector } from 'react-redux';
import { useFormik } from 'formik';
import * as Yup from 'yup';
import { Alert, IconButton, InputAdornment, Tooltip } from '@mui/material';
import '../styles/SignUp.css';
import {
  selectEmailLoginError,
  selectUserProfileStatus,
} from '../store/selectors';
import { getAuth, signInWithPopup, type UserCredential } from 'firebase/auth';
import {
  ACCOUNT_TARGET,
  COMPLETE_REGISTRATION_TARGET,
} from '../constants/Navigation';
import { VisibilityOffOutlined, VisibilityOutlined } from '@mui/icons-material';

export default function SignIn(): React.ReactElement {
  const dispatch = useAppDispatch();
  const navigateTo = useNavigate();
  const userProfileStatus = useSelector(selectUserProfileStatus);
  const emailLoginError = useSelector(selectEmailLoginError);
  const [showPassword, setShowPassword] = React.useState(false);

  const SignInSchema = Yup.object().shape({
    email: Yup.string().email().required('Email is required'),

    password: Yup.string()
      .required('Password is required')
      .min(12, 'Password is too short - should be 12 chars minimum'),
  });

  const formik = useFormik({
    initialValues: {
      email: '',
      password: '',
    },
    validationSchema: SignInSchema,
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
            onClick={() => formik.handleChange}
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
          Sign In With GitHub
        </Button>
      </Box>
    </Container>
  );
}
