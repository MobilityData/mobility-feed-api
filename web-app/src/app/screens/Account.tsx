import * as React from 'react';
import CssBaseline from '@mui/material/CssBaseline';
import {
  Typography,
  Container,
  IconButton,
  Button,
  Snackbar,
} from '@mui/material';
import { Visibility, VisibilityOff, ContentCopy } from '@mui/icons-material';

interface APIAccountState {
  apiKey: string;
  showApiKey: boolean;
}

export default function APIAccount(): React.ReactElement {
  const [values, setValues] = React.useState<APIAccountState>({
    apiKey: 'Your key is hidden',
    showApiKey: false,
  });
  const [openSnackbar, setOpenSnackbar] = React.useState(false);

  const handleClickShowApiKey = (): void => {
    setValues({
      ...values,
      showApiKey: !values.showApiKey,
      apiKey: values.showApiKey
        ? 'Your key is hidden'
        : 'your-api-key-here-12345',
    });
  };

  const handleCopyToClipboard = (): void => {
    navigator.clipboard
      .writeText('your-api-key-here-12345')
      .then(() => {
        setOpenSnackbar(true);
      })
      .catch((error) => {
        console.error('Could not copy text: ', error);
      });
  };

  return (
    <Container component='main' sx={{ mt: 12 }}>
      <CssBaseline />
      <Typography
        component='h1'
        variant='h5'
        color='secondary'
        sx={{ fontWeight: 'bold' }}
      >
        Your API Account
      </Typography>
      <Typography
        component='h2'
        variant='h6'
        color='primary'
        sx={{ mt: 2, fontWeight: 'bold' }}
      >
        User Details
      </Typography>
      <Typography variant='body1'>
        <b>Name:</b> John Doe
      </Typography>
      <Typography variant='body1'>
        <b>Email:</b> johndoe@example.com
      </Typography>
      <Typography variant='body1'>
        <b>Organization:</b> ABC Corp
      </Typography>

      <Typography
        component='h2'
        variant='h6'
        color='primary'
        sx={{ mt: 2, fontWeight: 'bold' }}
      >
        API Key
      </Typography>
      <Typography
        width={250}
        variant='body1'
        sx={{
          display: 'inline-block',
          mr: 2,
          background: '#e6e6e6',
          padding: 1,
          borderRadius: 2,
        }}
      >
        {values.apiKey}
      </Typography>
      <IconButton
        aria-label='Copy API key to clipboard'
        edge='end'
        onClick={handleCopyToClipboard}
        sx={{ display: 'inline-block', verticalAlign: 'middle' }}
      >
        <ContentCopy />
      </IconButton>
      <IconButton
        aria-label='toggle API key visibility'
        onClick={handleClickShowApiKey}
        edge='end'
        sx={{ display: 'inline-block', verticalAlign: 'middle' }}
      >
        {values.showApiKey ? <VisibilityOff /> : <Visibility />}
      </IconButton>

      <Snackbar
        open={openSnackbar}
        autoHideDuration={2000}
        onClose={() => {
          setOpenSnackbar(false);
        }}
        message='Your API key is copied to your clipboard.'
        anchorOrigin={{ horizontal: 'center', vertical: 'bottom' }}
        action={
          <React.Fragment>
            <Button
              color='primary'
              size='small'
              onClick={() => {
                setOpenSnackbar(false);
              }}
            >
              OK
            </Button>
          </React.Fragment>
        }
      />
    </Container>
  );
}
