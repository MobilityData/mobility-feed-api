import * as React from 'react';
import Button from '@mui/material/Button';
import CssBaseline from '@mui/material/CssBaseline';
import TextField from '@mui/material/TextField';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';

export default function ChangePassword(): React.ReactElement {
  return (
    <Container
      component='main'
      sx={{ mt: 12, display: 'flex', flexDirection: 'column' }}
    >
      <CssBaseline />
      <Typography
        component='h1'
        variant='h5'
        color='secondary'
        sx={{ fontWeight: 'bold', textAlign: 'left' }}
      >
        Change Password
      </Typography>

      <TextField
        variant='outlined'
        margin='normal'
        required
        id='currentPassword'
        label='Current Password'
        name='currentPassword'
        type='password'
        autoFocus
        sx={{ width: '50%' }}
      />
      <TextField
        variant='outlined'
        margin='normal'
        required
        id='newPassword'
        label='New Password'
        name='newPassword'
        type='password'
        sx={{ width: '50%' }}
      />
      <TextField
        variant='outlined'
        margin='normal'
        required
        id='confirmNewPassword'
        label='Confirm New Password'
        name='confirmNewPassword'
        type='password'
        sx={{ width: '50%' }}
      />

      <Box sx={{ display: 'flex', justifyContent: 'left' }}>
        <Button
          type='submit'
          variant='contained'
          color='primary'
          sx={{ mt: 3, mb: 2 }}
        >
          Save Changes
        </Button>
      </Box>
    </Container>
  );
}
