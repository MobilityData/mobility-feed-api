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

export default function SignUp(): React.ReactElement {
  const handleSubmit = (event: React.FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
  };

  const navigateTo = useNavigate();

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
          API Sign Up
        </Typography>
        <Typography component='h5'>
          Already have an account? <Link href='/sign-in'>Sign In Here</Link>.
        </Typography>
        <Box component='form' onSubmit={handleSubmit} noValidate sx={{ mt: 1 }}>
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
          <TextField
            margin='normal'
            required
            fullWidth
            name='confirmPassword'
            label='Confirm Password'
            type='password'
            id='confirmPassword'
            autoComplete='new-password'
          />
          <FormControlLabel
            control={<Checkbox value='agreeToTerms' color='primary' />}
            label='I agree to the terms and conditions'
          />
        </Box>
        <Button
          type='submit'
          variant='contained'
          sx={{ mt: 3, mb: 2, alignSelf: 'center' }}
          onClick={() => {
            navigateTo('/contact-info');
          }}
        >
          Sign Up
        </Button>
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
          Sign Up With Google
        </Button>
        <Button
          variant='outlined'
          color='inherit'
          sx={{ mb: 2 }}
          startIcon={<GitHubIcon />}
        >
          Sign Up With GitHub
        </Button>
      </Box>
    </Container>
  );
}
