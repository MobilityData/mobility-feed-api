import * as React from 'react';
import { useEffect } from 'react';
import { useSelector } from 'react-redux';
import {
  Alert,
  Box,
  Button,
  Container,
  CssBaseline,
  Typography,
  colors,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import {
  selectIsAnonymous,
  selectIsAuthenticated,
  selectUserProfile,
} from '../../store/profile-selectors';
import FeedSubmissionStepper from './FeedSubmissionStepper';
import { useRemoteConfig } from '../../context/RemoteConfigProvider';
import Contribute from '../Contribute';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';

function Component(): React.ReactElement {
  const { t } = useTranslation('feeds');
  const location = useLocation();
  const [showLoginSuccess, setShowLoginSuccess] = React.useState(
    location.state?.from === 'registration',
  );
  const user = useSelector(selectUserProfile);
  const isAuthenticated = useSelector(selectIsAuthenticated);
  const isAuthenticatedOrAnonymous =
    isAuthenticated || useSelector(selectIsAnonymous);

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
        }}
      >
        {!isAuthenticated && (
          <>
            <Typography
              variant='h5'
              color='primary'
              sx={{ fontWeight: 'bold' }}
            >
              {t('form.addOrUpdateFeed')}
            </Typography>
            <Typography sx={{ my: 2 }}>{t('form.signUp')}</Typography>
            <Button variant='contained'>
              <a href='/sign-up?add_feed=true' className='btn-link'>
                {t('form.signUpAction')}
              </a>
            </Button>
          </>
        )}
        {isAuthenticated && (
          <>
            {showLoginSuccess && (
              <Alert
                icon={<CheckIcon fontSize='inherit' />}
                severity='success'
                sx={{ mb: 2 }}
                onClose={() => {
                  setShowLoginSuccess(false);
                }}
              >
                {t('form.loginSuccess')}
              </Alert>
            )}

            <Box
              sx={{
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
          </>
        )}
      </Box>
    </Container>
  );
}

export default function Home(): React.ReactElement {
  const { config } = useRemoteConfig();
  if (config.enableFeedSubmissionStepper) {
    return <Component />;
  }
  return <Contribute />;
}
