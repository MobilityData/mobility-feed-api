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
import { useAppDispatch } from '../hooks';
import { login, selectIsAuthenticated } from '../store/profile-reducer';
import { type EmailLogin } from '../types';
import { useSelector } from 'react-redux';

export default function SignIn(): React.ReactElement {
  const dispatch = useAppDispatch();
  const navigateTo = useNavigate();
  const isAuthenticated = useSelector(selectIsAuthenticated);

  const handleEmailLogin = (event: React.FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const emailLogin: EmailLogin = {
      email: data.get('email') != null ? (data.get('email') as string) : '',
      password:
        data.get('password') != null ? (data.get('password') as string) : '',
    };
    dispatch(login(emailLogin));
  };

  React.useEffect(() => {
    if (isAuthenticated) {
      navigateTo('/account');
    }
  }, [isAuthenticated]);

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
          color='secondary'
          fontWeight='bold'
        >
          API Sign In
        </Typography>
        <Typography component='h5'>
          Don&apos;t have an account? <Link href='/sign-up'>Register Here</Link>
          .
        </Typography>
        <Box
          component='form'
          onSubmit={handleEmailLogin}
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
          />
          <TextField
            margin='normal'
            required
            fullWidth
            name='password'
            label='Password'
            type='password'
            id='password'
            autoComplete='current-password'
          />
          <FormControlLabel
            control={<Checkbox value='remember' color='primary' />}
            label='Remember me'
            sx={{ width: '100%' }}
          />
          <Button
            type='submit'
            variant='contained'
            sx={{ mt: 3, mb: 2 }}
            onClick={() => handleEmailLogin}
            data-testid='signin'
          >
            Sign In
          </Button>
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
          color='inherit'
          sx={{ mb: 2 }}
          startIcon={<GoogleIcon />}
        >
          Sign In With Google
        </Button>
        <Button
          variant='outlined'
          color='inherit'
          sx={{ mb: 2 }}
          startIcon={<GitHubIcon />}
        >
          Sign In With GitHub
        </Button>
      </Box>
    </Container>
  );
}
