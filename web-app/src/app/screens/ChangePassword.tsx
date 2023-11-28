import * as React from 'react';
import Button from '@mui/material/Button';
import CssBaseline from '@mui/material/CssBaseline';
import TextField from '@mui/material/TextField';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import { useFormik } from 'formik';
import * as Yup from 'yup';
import { Alert } from '@mui/material';
import { passwordValidatioError } from '../types';

export default function ChangePassword(): React.ReactElement {
  const ChangePasswordSchema = Yup.object().shape({
    currentPassword: Yup.string()
      .required('Password is required')
      .matches(
        /^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[.;!@#$%^&*])(?=.{12,})/,
        passwordValidatioError,
      ),
    newPassword: Yup.string()
      .required('New Password is required')
      .min(12, 'Password is too short - should be 12 chars minimum'),
    confirmNewPassword: Yup.string()
      .required('Confirm New Password is required')
      .oneOf([Yup.ref('newPassword')], 'Passwords must match'),
  });

  const formik = useFormik({
    initialValues: {
      currentPassword: '',
      newPassword: '',
      confirmNewPassword: '',
    },
    validationSchema: ChangePasswordSchema,
    onSubmit: (values) => {
      // Handle form submission here
      // You might want to dispatch an action to change the password
    },
  });
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
      <Box
        component='form'
        onSubmit={formik.handleSubmit}
        noValidate
        sx={{
          mt: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'left',
        }}
      >
        <TextField
          variant='outlined'
          margin='normal'
          required
          id='currentPassword'
          label='Current Password'
          name='currentPassword'
          type='password'
          autoFocus
          value={formik.values.currentPassword}
          onChange={formik.handleChange}
          sx={{ width: '50%' }}
        />
        {formik.errors.currentPassword != null ? (
          <Alert severity='error'>{formik.errors.confirmNewPassword}</Alert>
        ) : null}
        <TextField
          variant='outlined'
          margin='normal'
          required
          id='newPassword'
          label='New Password'
          name='newPassword'
          type='password'
          value={formik.values.newPassword}
          onChange={formik.handleChange}
          sx={{ width: '50%' }}
        />
        {formik.errors.newPassword != null ? (
          <Alert severity='error'>{formik.errors.newPassword}</Alert>
        ) : null}
        <TextField
          variant='outlined'
          margin='normal'
          required
          id='confirmNewPassword'
          label='Confirm New Password'
          name='confirmNewPassword'
          type='password'
          value={formik.values.confirmNewPassword}
          onChange={formik.handleChange}
          sx={{ width: '50%' }}
        />
        {formik.errors.confirmNewPassword != null ? (
          <Alert severity='error'>{formik.errors.confirmNewPassword}</Alert>
        ) : null}
      </Box>

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
