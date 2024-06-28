import * as React from 'react';
import { useEffect } from 'react';
import { useSelector } from 'react-redux';
import { Box, Container, CssBaseline, Grid, Stepper } from '@mui/material';
import {
  selectIsAnonymous,
  selectIsAuthenticated,
  selectUserProfile,
} from '../../store/profile-selectors';
import FeedSubmissionFAQ from './FeedSubmissionFAQ';
import FeedSubmissionStepper from './FeedSubmissionStepper';

export default function FeedSubmission(): React.ReactElement {
  const user = useSelector(selectUserProfile);
  // const dispatch = useAppDispatch();
  const isAuthenticatedOrAnonymous =
    useSelector(selectIsAuthenticated) || useSelector(selectIsAnonymous);

  useEffect(() => {
    if (isAuthenticatedOrAnonymous && user?.accessToken !== undefined) {
      console.log();
    }
  }, [isAuthenticatedOrAnonymous]);

  return (
    <Container component='main' sx={{ width: '100vw', m: 0 }}>
      <CssBaseline />
      <Box
        sx={{ mt: 12, display: 'flex', flexDirection: 'column', m: 10 }}
        margin={{ xs: '0', sm: '80px' }}
      >
        <FeedSubmissionStepper />
        <>
          <Stepper />
        </>
        <Box
          sx={{
            width: '90vw',
            background: '#F8F5F5',
            borderRadius: '6px 0px 0px 6px',
            p: 5,
            color: 'black',
            fontSize: '18px',
            fontWeight: 700,
            mr: 0,
          }}
        >
          <Grid container>
            <Grid item>
              <FeedSubmissionFAQ />
            </Grid>
          </Grid>
        </Box>
      </Box>
    </Container>
  );
}
