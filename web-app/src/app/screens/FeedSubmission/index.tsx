import * as React from 'react';
import { useEffect } from 'react';
import { useSelector } from 'react-redux';
import { Box, Container, CssBaseline, Typography, colors } from '@mui/material';
import {
  selectIsAnonymous,
  selectIsAuthenticated,
  selectUserProfile,
} from '../../store/profile-selectors';
import FeedSubmissionStepper from './FeedSubmissionStepper';

export default function FeedSubmission(): React.ReactElement {
  const user = useSelector(selectUserProfile);
  const isAuthenticatedOrAnonymous =
    useSelector(selectIsAuthenticated) || useSelector(selectIsAnonymous);

  useEffect(() => {
    if (isAuthenticatedOrAnonymous && user?.accessToken !== undefined) {
      console.log('User is authenticated or anonymous');
    }
  }, [isAuthenticatedOrAnonymous]);

  return (
    <Container component='main' sx={{ my: 0, mx: 'auto' }}>
      <CssBaseline />
      <Box
        sx={{
          mt: 12,
          mx: 'auto',
          maxWidth: '85%',
          p: 3,
          background: colors.grey[100],
        }}
      >
        <Typography>
          Do you have any questions about how to submit a feed?{' '}
          <a href='/contribute-faq' style={{ fontWeight: 'bold' }}>
            Read our FAQ
          </a>
        </Typography>
      </Box>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          mx: 'auto',
          mb: '80px',
          maxWidth: '750px',
        }}
      >
        <Typography
          variant='h4'
          sx={{
            color: colors.blue.A700,
            fontWeight: 'bold',
            my: 3,
            ml: 5,
          }}
        >
          Add or update a feed
        </Typography>
        <FeedSubmissionStepper />
      </Box>
    </Container>
  );
}
