import React from 'react';
import '../styles/Footer.css';
import TwitterIcon from '@mui/icons-material/Twitter';
import { IconButton } from '@mui/material';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faSlack } from '@fortawesome/free-brands-svg-icons';
import { GitHub, LinkedIn } from '@mui/icons-material';
import { MOBILITY_DATA_LINKS } from '../constants/Navigation';

const Footer: React.FC = () => {
  const navigateTo = (link: string): void => {
    window.open(link, '_blank');
  };

  return (
    <footer className='footer'>
      <p style={{ margin: 0 }}>Maintained with &#128156; by MobilityData. .</p>
      <div style={{ margin: 0, display: 'flex', justifyContent: 'center' }}>
        <IconButton
          className='link-button'
          color='primary'
          onClick={() => {
            navigateTo(MOBILITY_DATA_LINKS.twitter);
          }}
        >
          <TwitterIcon />
        </IconButton>
        <IconButton
          className='link-button'
          color='primary'
          onClick={() => {
            navigateTo(MOBILITY_DATA_LINKS.slack);
          }}
        >
          <FontAwesomeIcon icon={faSlack} />
        </IconButton>
        <IconButton
          className='link-button'
          color='primary'
          onClick={() => {
            navigateTo(MOBILITY_DATA_LINKS.linkedin);
          }}
        >
          <LinkedIn />
        </IconButton>
        <IconButton
          className='link-button'
          color='primary'
          onClick={() => {
            navigateTo(MOBILITY_DATA_LINKS.github);
          }}
        >
          <GitHub />
        </IconButton>
      </div>
    </footer>
  );
};

export default Footer;
