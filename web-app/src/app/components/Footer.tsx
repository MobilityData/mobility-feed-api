import React from 'react';
import './Footer.css';
import Link from '@mui/material/Link';

const Footer: React.FC = () => {
  return (
    <footer className='footer'>
      <p>
        Maintained with &#128156; by MobilityData.{' '}
        <Link>Add or update a feed</Link> or <Link>help improve the API</Link>.
      </p>
    </footer>
  );
};

export default Footer;
