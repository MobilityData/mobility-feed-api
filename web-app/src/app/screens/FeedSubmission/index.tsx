import * as React from 'react';
import { useSelector } from 'react-redux';
import {
  Alert,
  Box,
  Button,
  Container,
  CssBaseline,
  Typography,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import { selectIsAuthenticated } from '../../store/profile-selectors';
import { useRemoteConfig } from '../../context/RemoteConfigProvider';
import Contribute from '../Contribute';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import FeedSubmissionForm from './Form';
import { MainPageHeader } from '../../styles/PageHeader.style';
import { ColoredContainer } from '../../styles/PageLayout.style';

function Component(): React.ReactElement {
  const { t } = useTranslation('feeds');
  const location = useLocation();
  const [showLoginSuccess, setShowLoginSuccess] = React.useState(
    location.state?.from === 'registration',
  );
  const isAuthenticated = useSelector(selectIsAuthenticated);

  return (
    <Container component='main' sx={{ my: 0, mx: 'auto' }}>
      <CssBaseline />
      <Box
        sx={{
          mx: 'auto',
        }}
      >
        {!isAuthenticated && (
          <>
            <MainPageHeader>{t('form.addOrUpdateFeed')}</MainPageHeader>
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

            <ColoredContainer>
              <Typography>
                Do you have any questions about how to submit a feed?{' '}
                <a
                  href='/contribute-faq'
                  style={{ fontWeight: 'bold' }}
                  target='blank'
                >
                  Read our FAQ
                </a>
              </Typography>
            </ColoredContainer>
            <Container maxWidth='md'>
              <MainPageHeader sx={{ my: 3 }}>
                Add or update a feed
              </MainPageHeader>
              <FeedSubmissionForm />
            </Container>
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
