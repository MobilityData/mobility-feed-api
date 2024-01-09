import * as React from 'react';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import { EmailOutlined, Sync } from '@mui/icons-material';
import { Alert, Button } from '@mui/material';
import { useDispatch, useSelector } from 'react-redux';
import { verifyEmail } from '../store/profile-reducer';
import {
  selectEmailVerificationError,
  selectIsVerificationEmailSent,
} from '../store/profile-selectors';
import { type AppError } from '../types';
export default function PostRegistration(): React.ReactElement {
  const dispatch = useDispatch();
  const selectResendEmailSuccess = useSelector(selectIsVerificationEmailSent);
  const selectResendEmailError = useSelector(selectEmailVerificationError);
  const [resendEmailSuccess, setResendEmailSuccess] = React.useState(false);
  const [resendEmailError, setResendEmailError] =
    React.useState<AppError | null>(null);
  React.useEffect(() => {
    setResendEmailSuccess(selectResendEmailSuccess);
  }, [selectResendEmailSuccess]);
  React.useEffect(() => {
    setResendEmailError(selectResendEmailError ?? null);
  }, [selectResendEmailError]);

  return (
    <Container component='main' maxWidth='sm'>
      <CssBaseline />
      <Box
        sx={{
          mt: 12,
          ml: 2,
          mr: 2,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Typography
          component='h1'
          variant='h5'
          color='primary'
          fontWeight='bold'
          sx={{ display: 'flex', alignItems: 'center' }}
        >
          <EmailOutlined sx={{ mr: 1 }} />
          <div>Check your email !</div>
        </Typography>
        <Typography color='primary'>
          Thank you for registering for an API Account on the Mobility Database.
        </Typography>
        <Box sx={{ mt: 2 }}>
          An email will be sent to you shortly confirming your account
          registration.
        </Box>
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
          <Button
            variant='contained'
            color='primary'
            startIcon={<Sync />}
            onClick={() => {
              dispatch(verifyEmail());
            }}
          >
            Resend Email
          </Button>
        </Box>
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
          {resendEmailSuccess ? (
            <Alert severity='success'>Email sent successfully</Alert>
          ) : null}
          {resendEmailError !== null ? (
            <Alert severity='error'>{resendEmailError?.message}</Alert>
          ) : null}
        </Box>
      </Box>
    </Container>
  );
}
