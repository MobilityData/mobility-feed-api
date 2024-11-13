import React from 'react';
import '../styles/Footer.css';
import TwitterIcon from '@mui/icons-material/Twitter';
import { Button, IconButton } from '@mui/material';
import { GitHub, LinkedIn, OpenInNew } from '@mui/icons-material';
import { MOBILITY_DATA_LINKS } from '../constants/Navigation';
import { fontFamily, theme } from '../Theme';

const SlackSvg = (
  <svg
    xmlns='http://www.w3.org/2000/svg'
    width='24px'
    height='24px'
    viewBox='0 0 24 24'
  >
    <path
      fill={theme.palette.primary.main}
      d='M6 15a2 2 0 0 1-2 2a2 2 0 0 1-2-2a2 2 0 0 1 2-2h2zm1 0a2 2 0 0 1 2-2a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2a2 2 0 0 1-2-2zm2-8a2 2 0 0 1-2-2a2 2 0 0 1 2-2a2 2 0 0 1 2 2v2zm0 1a2 2 0 0 1 2 2a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2a2 2 0 0 1 2-2zm8 2a2 2 0 0 1 2-2a2 2 0 0 1 2 2a2 2 0 0 1-2 2h-2zm-1 0a2 2 0 0 1-2 2a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2a2 2 0 0 1 2 2zm-2 8a2 2 0 0 1 2 2a2 2 0 0 1-2 2a2 2 0 0 1-2-2v-2zm0-1a2 2 0 0 1-2-2a2 2 0 0 1 2-2h5a2 2 0 0 1 2 2a2 2 0 0 1-2 2z'
    />
  </svg>
);

const Footer: React.FC = () => {
  const navigateTo = (link: string): void => {
    window.open(link, '_blank');
  };

  return (
    <footer className='footer' style={{ fontFamily: fontFamily.secondary }}>
      <a
        href={'https://share.mobilitydata.org/mobility-database-feedback'}
        target={'_blank'}
        rel='noreferrer'
        className={'btn-link'}
      >
        <Button
          sx={{
            textTransform: 'none',
            mb: 2,
            fontFamily: fontFamily.secondary,
          }}
          variant={'outlined'}
          endIcon={<OpenInNew />}
        >
          Help Us by Sharing Feedback
        </Button>
      </a>
      <div style={{ margin: 0, display: 'flex', justifyContent: 'center' }}>
        <IconButton
          aria-label='twitter'
          className='link-button'
          color='primary'
          onClick={() => {
            navigateTo(MOBILITY_DATA_LINKS.twitter);
          }}
        >
          <TwitterIcon />
        </IconButton>
        <IconButton
          aria-label='slack'
          className='link-button'
          color='primary'
          onClick={() => {
            navigateTo(MOBILITY_DATA_LINKS.slack);
          }}
        >
          {SlackSvg}
        </IconButton>
        <IconButton
          aria-label='linkedin'
          className='link-button'
          color='primary'
          onClick={() => {
            navigateTo(MOBILITY_DATA_LINKS.linkedin);
          }}
        >
          <LinkedIn />
        </IconButton>
        <IconButton
          aria-label='github'
          className='link-button'
          color='primary'
          onClick={() => {
            navigateTo(MOBILITY_DATA_LINKS.github);
          }}
        >
          <GitHub />
        </IconButton>
      </div>
      <p style={{ margin: 0 }}>Maintained with &#128156; by MobilityData.</p>
      <p style={{ margin: 0 }}>
        <a href={'/privacy-policy'} target={'_blank'} rel={'noreferrer'}>
          Privacy Policy
        </a>
      </p>
      <p style={{ margin: 0 }}>
        <a href={'/terms-and-conditions'} target={'_blank'} rel={'noreferrer'}>
          Terms and Conditions
        </a>
      </p>
    </footer>
  );
};

export default Footer;
