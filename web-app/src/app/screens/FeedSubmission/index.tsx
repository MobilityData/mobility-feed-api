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
import { useTranslations } from 'next-intl';
import { useLocation } from 'react-router-dom';
import FeedSubmissionForm from './Form';
import { MainPageHeader } from '../../styles/PageHeader.style';
import { ColoredContainer } from '../../styles/PageLayout.style';

function Component(): React.ReactElement {
  const t = useTranslations('feeds');
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
            <Button variant='contained' href='/sign-up?add_feed=true'>
              {t('form.signUpAction')}
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
                Do you have any questions about how to submit a feed?
                <Button
                  variant='text'
                  className='inline'
                  sx={{ fontWeight: 700 }}
                  href={'/contribute-faq'}
                  rel='noreferrer'
                  target='_blank'
                >
                  Read our FAQ
                </Button>
                <br /> <br />
                Want to submit a GBFS feed to the Mobility Database? Contribute
                through the&#20;
                <Button
                  variant='text'
                  className='line-start inline'
                  sx={{ fontWeight: 700 }}
                  href={
                    'https://github.com/MobilityData/gbfs?tab=readme-ov-file#systems-catalog---systems-implementing-gbfs'
                  }
                  rel='noreferrer'
                  target='_blank'
                >
                  GBFS systems catalog
                </Button>
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
  return <Component />;
}
