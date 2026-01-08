import * as React from 'react';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import { Button, Card, styled, Typography, useTheme } from '@mui/material';
import EmailIcon from '@mui/icons-material/Email';
import GitHubIcon from '@mui/icons-material/GitHub';
import { useTranslations } from 'next-intl';

const ContactUsItem = styled(Card)(({ theme }) => ({
  padding: theme.spacing(2),
  margin: theme.spacing(1),
  textAlign: 'center',
  width: '100%',
  [theme.breakpoints.up('sm')]: {
    width: 'calc(50% - 50px)',
  },
  '.item-container': {
    textAlign: 'center',
  },
  '.mui-icon': {
    fontSize: '4rem',
  },
  '.text-body': {
    textAlign: 'left',
    padding: `0 ${theme.spacing(2)}`,
  },
  '.action-button': {
    margin: theme.spacing(1),
    marginTop: theme.spacing(2),
  },
}));

export default function ContactUs(): React.ReactElement {
  const t = useTranslations('contactUs');
  const theme = useTheme();
  const SlackSvg = (
    <svg
      xmlns='http://www.w3.org/2000/svg'
      width='4rem'
      height='4rem'
      viewBox='0 0 24 24'
    >
      <path
        fill={theme.palette.primary.main}
        d='M6 15a2 2 0 0 1-2 2a2 2 0 0 1-2-2a2 2 0 0 1 2-2h2zm1 0a2 2 0 0 1 2-2a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2a2 2 0 0 1-2-2zm2-8a2 2 0 0 1-2-2a2 2 0 0 1 2-2a2 2 0 0 1 2 2v2zm0 1a2 2 0 0 1 2 2a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2a2 2 0 0 1 2-2zm8 2a2 2 0 0 1 2-2a2 2 0 0 1 2 2a2 2 0 0 1-2 2h-2zm-1 0a2 2 0 0 1-2 2a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2a2 2 0 0 1 2 2zm-2 8a2 2 0 0 1 2 2a2 2 0 0 1-2 2a2 2 0 0 1-2-2v-2zm0-1a2 2 0 0 1-2-2a2 2 0 0 1 2-2h5a2 2 0 0 1 2 2a2 2 0 0 1-2 2z'
      />
    </svg>
  );
  return (
    <Container component='main' maxWidth={'lg'}>
      <Typography variant='h1'>{t('title')}</Typography>
      <Box
        sx={{
          mt: 2,
          display: 'flex',
          flexWrap: 'wrap',
        }}
      >
        <ContactUsItem variant='outlined'>
          <Box className='item-container'>
            <EmailIcon color='primary' className='mui-icon' />
            <Typography variant='h6' color='primary' sx={{ fontWeight: 700 }}>
              {t('email.title')}
            </Typography>
          </Box>
          <Typography variant='body1'>
            {t('email.description')}
            <Button
              variant='text'
              className='inline'
              href={'mailto:api@mobilitydata.org'}
            >
              api@mobilitydata.org
            </Button>
          </Typography>
        </ContactUsItem>

        <ContactUsItem variant='outlined'>
          <Box className='item-container'>
            {SlackSvg}
            <Typography variant='h6' color='primary' sx={{ fontWeight: 700 }}>
              {t('slack.title')}
            </Typography>
          </Box>
          <Typography variant='body1'>{t('slack.description')}</Typography>
          <Button
            variant={'contained'}
            className='action-button'
            href='https://share.mobilitydata.org/slack'
            target='_blank'
            rel='noopener noreferrer'
          >
            {t('slack.action')}
          </Button>
        </ContactUsItem>

        <ContactUsItem variant='outlined'>
          <Box className='item-container'>
            <GitHubIcon color='primary' className='mui-icon' />
            <Typography variant='h6' color='primary' sx={{ fontWeight: 700 }}>
              {t('contribute.title')}
            </Typography>
          </Box>
          <Typography variant='body1' className='text-body'>
            {t('contribute.description')}
          </Typography>
          <Button
            variant={'contained'}
            className='action-button'
            href='https://github.com/MobilityData/mobility-feed-api'
            target='_blank'
            rel='noopener noreferrer'
          >
            {t('contribute.action')}
          </Button>
        </ContactUsItem>

        <ContactUsItem variant='outlined'>
          <Box className='item-container'>
            <GitHubIcon color='primary' className='mui-icon' />
            <Typography variant='h6' color='primary' sx={{ fontWeight: 700 }}>
              {t('addFeeds.title')}
            </Typography>
          </Box>
          <Typography variant='body1' className='text-body'>
            {t('addFeeds.description')}
          </Typography>
          <Button
            variant={'contained'}
            className='action-button'
            href='https://github.com/MobilityData/mobility-database-catalogs'
            target='_blank'
            rel='noopener noreferrer'
          >
            {t('addFeeds.action')}
          </Button>
        </ContactUsItem>
      </Box>
    </Container>
  );
}
