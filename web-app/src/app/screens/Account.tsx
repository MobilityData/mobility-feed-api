import * as React from 'react';
import CssBaseline from '@mui/material/CssBaseline';
import '../styles/Account.css';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '@mui/material/styles';
import {
  Typography,
  Container,
  IconButton,
  Button,
  Link,
  Paper,
  Box,
  Tooltip,
  Alert,
  CircularProgress,
  Snackbar,
  Chip,
} from '@mui/material';
import {
  AccountCircleOutlined,
  Check,
  ContentCopyOutlined,
  ExitToAppOutlined,
  RefreshOutlined,
  VisibilityOffOutlined,
  VisibilityOutlined,
  WarningAmberOutlined,
} from '@mui/icons-material';
import { useSelector } from 'react-redux';
import {
  selectIsRefreshingAccessToken,
  selectRefreshingAccessTokenError,
  selectUserProfile,
  selectSignedInWithProvider,
} from '../store/selectors';
import LogoutConfirmModal from '../components/LogoutConfirmModal';
import { useAppDispatch } from '../hooks';
import { requestRefreshAccessToken } from '../store/profile-reducer';
import {
  formatTokenExpiration,
  getTimeLeftForTokenExpiration,
} from '../utils/date';

interface APIAccountState {
  showRefreshToken: boolean;
  showAccessToken: boolean;
  codeBlockTooltip: string;
  tokenExpired: boolean;
}

enum TokenTypes {
  Access = 'accessToken',
  Refresh = 'refreshToken',
}

const texts = {
  accessTokenHidden: 'Your access token is hidden',
  refreshTokenHidden: 'Your refresh token is hidden',
  copyAccessToken: 'Copy Access Token',
  copyAccessTokenToClipboard: 'Copy access token to clipboard',
  copyRefreshToken: 'Copy Refresh Token',
  copyRefreshTokenToClipboard: 'Copy refresh token to clipboard',
  copyToClipboard: 'Copy to clipboard',
  copied: 'Copied!',
  tokenUnavailable: 'Your token is unavailable',
};

export default function APIAccount(): React.ReactElement {
  const apiURL = 'https://api.mobilitydatabase.org/v1';
  const dispatch = useAppDispatch();
  const theme = useTheme();
  const user = useSelector(selectUserProfile);
  const navigateTo = useNavigate();
  const refreshingAccessTokenError = useSelector(
    selectRefreshingAccessTokenError,
  );
  const isRefreshingAccessToken = useSelector(selectIsRefreshingAccessToken);
  const signedInWithProvider = useSelector(selectSignedInWithProvider);
  const [accountState, setAccountState] = React.useState<APIAccountState>({
    showRefreshToken: false,
    showAccessToken: false,
    codeBlockTooltip: texts.copyToClipboard,
    tokenExpired: false,
  });

  const [timeLeftForTokenExpiration, setTimeLeftForTokenExpiration] =
    React.useState<string>('');
  const [openDialog, setOpenDialog] = React.useState<boolean>(false);
  const [showAccessTokenCopiedTooltip, setShowAccessTokenCopiedTooltip] =
    React.useState(false);
  const [showAccessTokenSnackbar, setShowAccessTokenSnackbar] =
    React.useState(false);
  const [accessTokenCopyResult, setAccessTokenCopyResult] =
    React.useState<string>('');
  const [showRefreshTokenCopiedTooltip, setShowRefreshTokenCopiedTooltip] =
    React.useState(false);
  const [refreshTokenCopyResult, setRefreshTokenCopyResult] =
    React.useState<string>('');

  const showGenerateAccessTokenButton = React.useMemo(() => {
    return user?.accessToken == null;
  }, [user?.accessToken]);

  React.useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    const accessTokenExpirationTime = user?.accessTokenExpirationTime;
    if (accessTokenExpirationTime !== undefined) {
      interval = setInterval(() => {
        const expirationTime = getTimeLeftForTokenExpiration(
          accessTokenExpirationTime,
        );
        let formattedExpirationTime = '';
        if (!expirationTime.future) {
          clearInterval(interval as NodeJS.Timeout);
          setAccountState({ ...accountState, tokenExpired: true });
        } else {
          formattedExpirationTime = formatTokenExpiration(
            expirationTime.duration,
          );
        }
        setTimeLeftForTokenExpiration(formattedExpirationTime);
      }, 250);
    }

    return () => {
      if (interval !== null) {
        clearInterval(interval);
      }
    };
  }, [user?.accessTokenExpirationTime]);

  React.useEffect(() => {
    setShowAccessTokenSnackbar(refreshingAccessTokenError !== null);
  }, [refreshingAccessTokenError]);

  const handleClickShowToken = React.useCallback(
    (tokenType: TokenTypes): void => {
      switch (tokenType) {
        case TokenTypes.Access:
          setAccountState({
            ...accountState,
            showAccessToken: !accountState.showAccessToken,
          });
          break;
        case TokenTypes.Refresh:
          setAccountState({
            ...accountState,
            showRefreshToken: !accountState.showRefreshToken,
          });
          break;
      }
    },
    [accountState],
  );

  const handleCopyTokenToClipboard = React.useCallback(
    (
      token: string,
      setResult: (result: string) => void,
      setShowTooltip: (showToolTip: boolean) => void,
    ): void => {
      navigator.clipboard
        .writeText(token)
        .then(() => {
          setResult(texts.copied);
        })
        .catch((error) => {
          setResult(`Could not copy text: ${error}`);
        })
        .finally(() => {
          setShowTooltip(true);
          setTimeout(() => {
            setShowTooltip(false);
          }, 1000);
        });
    },
    [],
  );

  const handleGenerateAccessToken = (): void => {
    setAccountState({
      ...accountState,
      tokenExpired: false,
    });
    dispatch(requestRefreshAccessToken());
  };

  const getCurlAccessTokenCommand = (): string => {
    const refreshToken =
      user?.refreshToken !== undefined
        ? user?.refreshToken
        : '[Your Refresh Token]';
    return `curl --location '${apiURL}/tokens' --header 'Content-Type: application/json' --data '{ "refresh_token": "${refreshToken}" }'`;
  };

  const getCurlApiTestCommand = (): string => {
    const accessToken =
      user?.accessToken !== undefined
        ? user?.accessToken
        : '[Your Access Token]';
    return `curl --location '${apiURL}/metadata' --header 'Accept: application/json' --header 'Authorization: Bearer ${accessToken}'`;
  };

  const handleCopyCodeBlock = (codeBlock: string): void => {
    navigator.clipboard
      .writeText(codeBlock)
      .then(() => {
        setAccountState({
          ...accountState,
          codeBlockTooltip: 'Copied!',
        });
        setTimeout(() => {
          setAccountState({
            ...accountState,
            codeBlockTooltip: 'Copy to clipboard',
          });
        }, 1000);
      })
      .catch((error) => {
        console.log('Could not copy text: ', error);
      });
  };

  function handleSignOutClick(): void {
    setOpenDialog(true);
  }

  function handleChangePasswordClick(): void {
    navigateTo('/change-password');
  }

  const refreshAccessTokenButtonText = isRefreshingAccessToken
    ? 'Refreshing Access token...'
    : 'Refresh Access token';

  return (
    <Container
      component={'main'}
      maxWidth={false}
      sx={{
        mt: 12,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      <Snackbar
        open={showAccessTokenSnackbar}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        autoHideDuration={6000}
        onClose={() => {
          setShowAccessTokenSnackbar(false);
        }}
      >
        <Alert
          severity='error'
          onClose={() => {
            setShowAccessTokenSnackbar(false);
          }}
        >
          {refreshingAccessTokenError?.message ?? ''}
        </Alert>
      </Snackbar>
      <CssBaseline />
      <Typography
        component='h1'
        variant='h4'
        color='primary'
        sx={{ fontWeight: 'bold', ml: 5 }}
        alignSelf='flex-start'
      >
        Your API Account
      </Typography>
      <Box sx={{ display: 'flex', width: '100%', mt: 2 }}>
        <Paper
          sx={{
            bgcolor: '#f9f5f5',
            width: '390px',
            p: 3,
            mr: 1,
            display: 'flex',
            flexDirection: 'column',
          }}
          elevation={0}
        >
          <Typography
            component='h5'
            variant='h5'
            color='primary'
            sx={{
              fontWeight: 'bold',
              mb: 1,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <AccountCircleOutlined sx={{ mr: 1 }} />
            User Details
          </Typography>
          <Typography variant='body1'>
            <b>Name:</b>
            {' ' + user?.fullName ?? 'Unknown'}
          </Typography>
          <Typography variant='body1'>
            {user?.email !== undefined && user?.email !== '' ? (
              <Typography variant='body1'>
                <b>Email:</b> {' ' + user?.email ?? 'Unknown'}
              </Typography>
            ) : null}
          </Typography>
          <Typography variant='body1'>
            <b>Organization:</b> {' ' + user?.organization ?? 'Unknown'}
          </Typography>
          {user?.isRegisteredToReceiveAPIAnnouncements === true ? (
            <Chip
              label='Registered to API Announcements'
              color='primary'
              variant='outlined'
              sx={{ mt: 1 }}
              icon={<Check />}
            />
          ) : null}
          <Box sx={{ mt: 2 }} />
          <Box sx={{ display: 'flex', justifyContent: 'space-evenly' }}>
            {!signedInWithProvider && (
              <Button
                variant='contained'
                color='primary'
                sx={{ mt: 1, ml: 1 }}
                onClick={handleChangePasswordClick}
              >
                Change Password
              </Button>
            )}
            <Button
              variant='contained'
              color='primary'
              sx={{ mt: 1 }}
              startIcon={<ExitToAppOutlined />}
              onClick={handleSignOutClick}
            >
              Sign Out
            </Button>
          </Box>
          <Box sx={{ mt: 4 }} />
          <Typography>
            Want your account removed? Send us an email at{' '}
            <Link
              href='mailto:api@mobilitydata.org'
              color={'inherit'}
              fontWeight={'bold'}
            >
              api@mobilitydata.org
            </Link>
            .
          </Typography>
        </Paper>
        <Box sx={{ ml: 10 }}>
          <Box sx={{ width: 'fit-content', p: 1, mb: 5 }}>
            <Typography variant='sectionTitle'>Refresh Token</Typography>
            <Typography sx={{ mb: 2 }}>
              Use your refresh token to connect to the API in your app.
            </Typography>
            <Box className='token-display-element'>
              <Typography width={500} variant='body1'>
                {accountState.showRefreshToken
                  ? user?.refreshToken !== undefined
                    ? user?.refreshToken
                    : texts.tokenUnavailable
                  : texts.refreshTokenHidden}
              </Typography>
              <Box className='token-action-buttons'>
                <Tooltip
                  title={
                    showRefreshTokenCopiedTooltip
                      ? refreshTokenCopyResult
                      : texts.copyRefreshToken
                  }
                >
                  <span>
                    <IconButton
                      color='primary'
                      aria-label={texts.copyRefreshTokenToClipboard}
                      edge='end'
                      disabled={user?.refreshToken === undefined}
                      onClick={() => {
                        if (user?.refreshToken != null) {
                          handleCopyTokenToClipboard(
                            user.refreshToken,
                            setRefreshTokenCopyResult,
                            setShowRefreshTokenCopiedTooltip,
                          );
                        }
                      }}
                      sx={{
                        display: 'inline-block',
                        verticalAlign: 'middle',
                      }}
                    >
                      <ContentCopyOutlined fontSize='small' />
                    </IconButton>
                  </span>
                </Tooltip>
                <Tooltip title='Toggle Refresh Token Visibility'>
                  <IconButton
                    color='primary'
                    aria-label='toggle refresh token visibility'
                    onClick={() => {
                      handleClickShowToken(TokenTypes.Refresh);
                    }}
                    edge='end'
                    sx={{ display: 'inline-block', verticalAlign: 'middle' }}
                  >
                    {accountState.showRefreshToken ? (
                      <VisibilityOffOutlined fontSize='small' />
                    ) : (
                      <VisibilityOutlined fontSize='small' />
                    )}
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>
          </Box>
          <Box sx={{ mb: 1 }}>
            <Typography variant='sectionTitle'>
              Access Token for Testing
            </Typography>
            <Typography sx={{ mb: 2 }}>
              Want some quick testing? Copy the access token bellow to test
              endpoints in our Swagger documentation.
              <br />
              The access token updates regularly.
            </Typography>
            {showGenerateAccessTokenButton && (
              <Box sx={{ mb: 2 }}>
                <Button onClick={handleGenerateAccessToken} variant='contained'>
                  Generate Access Token
                </Button>
              </Box>
            )}

            {!showGenerateAccessTokenButton && (
              <Box sx={{ width: 'fit-content', p: 1, mb: 5 }}>
                <Box className='token-display-element'>
                  <Typography width={500} variant='body1'>
                    {accountState.showAccessToken
                      ? user?.accessToken !== undefined
                        ? user?.accessToken
                        : texts.tokenUnavailable
                      : texts.accessTokenHidden}
                  </Typography>
                  <Box className='token-action-buttons'>
                    <Tooltip title={refreshAccessTokenButtonText}>
                      <span>
                        <IconButton
                          color='primary'
                          aria-label={refreshAccessTokenButtonText}
                          edge='end'
                          sx={{
                            display: 'inline-block',
                            verticalAlign: 'middle',
                          }}
                          onClick={handleGenerateAccessToken}
                          disabled={isRefreshingAccessToken}
                        >
                          {isRefreshingAccessToken ? (
                            <CircularProgress size={14} />
                          ) : (
                            <RefreshOutlined
                              fontSize='small'
                              sx={{
                                display: 'inline-block',
                                verticalAlign: 'middle',
                              }}
                            />
                          )}
                        </IconButton>
                      </span>
                    </Tooltip>

                    <Tooltip
                      title={
                        showAccessTokenCopiedTooltip
                          ? accessTokenCopyResult
                          : texts.copyAccessToken
                      }
                    >
                      <span>
                        <IconButton
                          color='primary'
                          aria-label={texts.copyAccessTokenToClipboard}
                          edge='end'
                          disabled={user?.accessToken === undefined}
                          onClick={() => {
                            if (user?.accessToken != null) {
                              handleCopyTokenToClipboard(
                                user.accessToken,
                                setAccessTokenCopyResult,
                                setShowAccessTokenCopiedTooltip,
                              );
                            }
                          }}
                          sx={{
                            display: 'inline-block',
                            verticalAlign: 'middle',
                          }}
                        >
                          <ContentCopyOutlined
                            fontSize='small'
                            sx={{
                              display: 'inline-block',
                              verticalAlign: 'middle',
                            }}
                          />
                        </IconButton>
                      </span>
                    </Tooltip>
                    <Tooltip title='Toggle Access Token Visibility'>
                      <IconButton
                        color='primary'
                        aria-label='Toggle access token visibility'
                        edge='end'
                        onClick={() => {
                          handleClickShowToken(TokenTypes.Access);
                        }}
                        sx={{
                          display: 'inline-block',
                          verticalAlign: 'middle',
                        }}
                      >
                        {accountState.showAccessToken ? (
                          <VisibilityOffOutlined
                            fontSize='small'
                            sx={{
                              display: 'inline-block',
                              verticalAlign: 'middle',
                            }}
                          />
                        ) : (
                          <VisibilityOutlined
                            fontSize='small'
                            sx={{
                              display: 'inline-block',
                              verticalAlign: 'middle',
                            }}
                          />
                        )}
                      </IconButton>
                    </Tooltip>
                  </Box>
                </Box>
                <Typography color='error' sx={{ mb: 2 }}>
                  <WarningAmberOutlined style={{ verticalAlign: 'bottom' }} />
                  {accountState.tokenExpired
                    ? 'Token expired'
                    : `Your token will expire in ${timeLeftForTokenExpiration}`}
                  .
                </Typography>
              </Box>
            )}
          </Box>
          <Paper elevation={3} id='code-block'>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '10px',
              }}
            >
              <div>
                <Typography variant='h6'>API Test</Typography>

                <Typography>
                  Copy the CLI command to test your access to the API.
                </Typography>
              </div>
              <Tooltip title={accountState.codeBlockTooltip}>
                <IconButton
                  color='inherit'
                  aria-label='Copy access token to clipboard'
                  edge='end'
                  onClick={() => {
                    handleCopyCodeBlock(getCurlApiTestCommand());
                  }}
                  sx={{ display: 'inline-block', verticalAlign: 'middle' }}
                >
                  <ContentCopyOutlined fontSize='small' />
                </IconButton>
              </Tooltip>
            </div>
            <Typography id='code-block-content'>
              <span style={{ color: '#ff79c6', fontWeight: 'bold' }}>curl</span>{' '}
              --location &apos;{apiURL}/metadata&apos;
              <span style={{ color: theme.mixins.code?.contrastText }}>\</span>
              <br />
              <span style={{ color: theme.mixins.code?.contrastText }}>
                --header
              </span>{' '}
              &apos;Accept: application/json&apos;
              <span style={{ color: theme.mixins.code?.contrastText }}>\</span>
              <br />
              <span style={{ color: theme.mixins.code?.contrastText }}>
                --header
              </span>
              &apos;Authorization: Bearer [Your Access Token]&apos;
            </Typography>
          </Paper>
          <Box sx={{ p: 1, mt: 5 }}>
            <Typography variant='sectionTitle'>
              How to Get the Access Token in Your App
            </Typography>
            <Typography sx={{ mb: 2 }}>
              Follow{' '}
              <Link
                href='https://mobilitydata.github.io/mobility-feed-api/SwaggerUI/index.html'
                color={'inherit'}
                target='_blank'
              >
                our Swagger documentation
              </Link>{' '}
              to authenticate your account with the refresh token.
            </Typography>
            <Paper elevation={3} id='code-block'>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '10px',
                }}
              >
                <div>
                  <Typography variant='h6'>Generate Access Token</Typography>

                  <Typography>
                    Copy the CLI command to generate an access token.
                  </Typography>
                </div>
                <Tooltip title={accountState.codeBlockTooltip}>
                  <IconButton
                    color='inherit'
                    aria-label='Copy access token to clipboard'
                    edge='end'
                    onClick={() => {
                      handleCopyCodeBlock(getCurlAccessTokenCommand());
                    }}
                    sx={{ display: 'inline-block', verticalAlign: 'middle' }}
                  >
                    <ContentCopyOutlined fontSize='small' />
                  </IconButton>
                </Tooltip>
              </div>
              <Typography id='code-block-content'>
                <span style={{ ...theme.mixins.code.command }}>curl</span>{' '}
                --location &apos;{apiURL}/tokens&apos;
                <span style={{ color: theme.mixins.code?.contrastText }}>
                  \
                </span>
                <br />
                <span style={{ color: theme.mixins.code?.contrastText }}>
                  --header
                </span>{' '}
                &apos;Content-Type: application/json&apos;
                <span style={{ color: theme.mixins.code?.contrastText }}>
                  \
                </span>
                <br />
                <span style={{ color: theme.mixins.code?.contrastText }}>
                  --data &apos;&#123;
                </span>
                <span>
                  {' '}
                  &quot;refresh_token&quot;: &quot;[Your Refresh Token]&quot;
                </span>
                <span style={{ color: theme.mixins.code?.contrastText }}>
                  {' '}
                  &#125;&apos;
                </span>
              </Typography>
            </Paper>
          </Box>
        </Box>
      </Box>
      <LogoutConfirmModal
        openDialog={openDialog}
        setOpenDialog={setOpenDialog}
      />
    </Container>
  );
}
