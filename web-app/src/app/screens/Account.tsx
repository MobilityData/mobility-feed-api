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
import { useSelector } from 'react-redux';
import { selectUserProfile } from '../store/selectors';
interface APIAccountState {
  refreshToken: string;
  showRefreshToken: boolean;
  accessToken: string;
  showAccessToken: boolean;
}

export default function APIAccount(): React.ReactElement {
  const [values, setValues] = React.useState<APIAccountState>({
    refreshToken: 'Your refresh token is hidden',
    showRefreshToken: false,
    accessToken: 'Your access token is hidden',
    showAccessToken: false,
  });
  const user = useSelector(selectUserProfile);
  const [openSnackbar, setOpenSnackbar] = React.useState(false);

  const handleClickShowApiKey = (tokenType: 'access' | 'refresh'): void => {
    switch (tokenType) {
      case 'access':
        setValues({
          ...values,
          showAccessToken: !values.showAccessToken,
          accessToken: values.showAccessToken
            ? 'Your access token is hidden'
            : user?.accessToken ?? 'Your access token is unavailable',
        });
        break;
      case 'refresh':
        setValues({
          ...values,
          showRefreshToken: !values.showRefreshToken,
          refreshToken: values.showRefreshToken
            ? 'Your refresh token is hidden'
            : user?.refreshToken ?? 'Your refresh token is unavailable',
        });
        break;
      default:
        break;
    }
  };

  const handleCopyToClipboard = (token: string): void => {
    navigator.clipboard
      .writeText(token)
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
        Refresh Token
      </Typography>
      <Typography
        variant='body1'
        // width='100%'
        sx={{
          display: 'inline-block',
          mr: 2,
          background: '#e6e6e6',
          padding: 1,
          borderRadius: 2,
          wordBreak: 'break-word',
        }}
      >
        {values.refreshToken}
      </Typography>
      <IconButton
        aria-label='Copy Refresh Token to clipboard'
        edge='end'
        onClick={() => {
          handleCopyToClipboard(values.refreshToken);
        }}
        sx={{ display: 'inline-block', verticalAlign: 'middle' }}
      >
        <ContentCopy />
      </IconButton>
      <IconButton
        aria-label='toggle Refresh Token visibility'
        onClick={() => {
          handleClickShowApiKey('refresh');
        }}
        edge='end'
        sx={{ display: 'inline-block', verticalAlign: 'middle' }}
      >
        {values.showRefreshToken ? <VisibilityOff /> : <Visibility />}
      </IconButton>

      <Snackbar
        open={openSnackbar}
        autoHideDuration={2000}
        onClose={() => {
          setOpenSnackbar(false);
        }}
        message='Your Refresh Token is copied to your clipboard.'
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

      <Typography
        component='h2'
        variant='h6'
        color='primary'
        sx={{ mt: 2, fontWeight: 'bold' }}
      >
        Access Token
      </Typography>
      <Typography
        variant='body1'
        sx={{
          display: 'inline-block',
          mr: 2,
          background: '#e6e6e6',
          padding: 1,
          borderRadius: 2,
          wordBreak: 'break-word',
        }}
      >
        {values.accessToken}
      </Typography>
      <IconButton
        aria-label='Copy Access Token to clipboard'
        edge='end'
        onClick={() => {
          handleCopyToClipboard(values.accessToken);
        }}
        sx={{ display: 'inline-block', verticalAlign: 'middle' }}
      >
        <ContentCopy />
      </IconButton>
      <IconButton
        aria-label='toggle Access Token visibility'
        onClick={() => {
          handleClickShowApiKey('access');
        }}
        edge='end'
        sx={{ display: 'inline-block', verticalAlign: 'middle' }}
      >
        {values.showAccessToken ? <VisibilityOff /> : <Visibility />}
      </IconButton>

      <Snackbar
        open={openSnackbar}
        autoHideDuration={2000}
        onClose={() => {
          setOpenSnackbar(false);
        }}
        message='Your Access Token is copied to your clipboard.'
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
