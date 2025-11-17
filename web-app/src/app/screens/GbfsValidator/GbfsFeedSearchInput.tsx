import { OpenInNew } from '@mui/icons-material';
import {
  Box,
  TextField,
  Button,
  FormGroup,
  FormControlLabel,
  Checkbox,
  useTheme,
  Container,
  FormControl,
  MenuItem,
  Select,
  type SelectChangeEvent,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthTypeEnum, useGbfsAuth } from '../../context/GbfsAuthProvider';
import { useSelector } from 'react-redux';
import { selectGbfsValidationParams } from '../../store/gbfs-validator-selectors';

interface GbfsFeedSearchInputProps {
  initialFeedUrl?: string;
  triggerDataFetch?: () => void;
}

export default function GbfsFeedSearchInput({
  initialFeedUrl,
  triggerDataFetch,
}: GbfsFeedSearchInputProps): React.ReactElement {
  const lastSearchParams = useSelector(selectGbfsValidationParams);
  const theme = useTheme();
  const navigate = useNavigate();
  const { auth, setAuth } = useGbfsAuth();
  const [autoDiscoveryUrlInput, setAutoDiscoveryUrlInput] = useState<string>(
    initialFeedUrl ?? '',
  );
  const [requiresAuth, setRequiresAuth] = useState(false);
  const [authType, setAuthType] = useState<string>('');
  const [basicAuthUsername, setBasicAuthUsername] = useState<
    string | undefined
  >(undefined);
  const [basicAuthPassword, setBasicAuthPassword] = useState<
    string | undefined
  >(undefined);
  const [bearerAuthValue, setBearerAuthValue] = useState<string | undefined>(
    undefined,
  );
  const [oauthClientId, setOauthClientId] = useState<string | undefined>(
    undefined,
  );
  const [oauthClientSecret, setOauthClientSecret] = useState<
    string | undefined
  >(undefined);
  const [oauthTokenUrl, setOauthTokenUrl] = useState<string | undefined>(
    undefined,
  );

  // Used to keep the text input up to date with back navigation in browser
  useEffect(() => {
    setAutoDiscoveryUrlInput(initialFeedUrl ?? '');
  }, [initialFeedUrl]);

  // Used to keep the auth inputs up to date
  useEffect(() => {
    setRequiresAuth(auth !== undefined);
    setAuthType(auth == undefined ? '' : auth.authType ?? '');
    setBasicAuthUsername(
      auth != null && 'username' in auth ? auth.username : undefined,
    );
    setBasicAuthPassword(
      auth != null && 'password' in auth ? auth.password : undefined,
    );
    setBearerAuthValue(
      auth != null && 'token' in auth ? auth.token : undefined,
    );
    setOauthClientId(
      auth != null && 'clientId' in auth ? auth.clientId : undefined,
    );
    setOauthClientSecret(
      auth != null && 'clientSecret' in auth ? auth.clientSecret : undefined,
    );
    setOauthTokenUrl(
      auth != null && 'tokenUrl' in auth ? auth.tokenUrl : undefined,
    );
  }, [auth]);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
    setRequiresAuth(event.target.checked);
  };

  const handleAuthTypeChange = (event: SelectChangeEvent<string>): void => {
    setAuthType(event.target.value);
    setBasicAuthUsername(undefined);
    setBasicAuthPassword(undefined);
    setBearerAuthValue(undefined);
    setOauthClientId(undefined);
    setOauthClientSecret(undefined);
    setOauthTokenUrl(undefined);
  };

  const isSubmitBoxDisabled = (): boolean => {
    if (autoDiscoveryUrlInput === '') return true;
    if (requiresAuth && authType === '') return true;
    return false;
  };

  const validateGBFSFeed = (): void => {
    if (requiresAuth) {
      switch (authType) {
        case AuthTypeEnum.BASIC:
          setAuth({
            authType: AuthTypeEnum.BASIC,
            username: basicAuthUsername,
            password: basicAuthPassword,
          });
          break;
        case AuthTypeEnum.BEARER:
          setAuth({ authType: AuthTypeEnum.BEARER, token: bearerAuthValue });
          break;
        case AuthTypeEnum.OAUTH:
          setAuth({
            authType: AuthTypeEnum.OAUTH,
            clientId: oauthClientId,
            clientSecret: oauthClientSecret,
            tokenUrl: oauthTokenUrl,
          });
          break;
        default:
          setAuth(undefined);
      }
    } else {
      setAuth(undefined);
    }

    // If the URL is the same React will ignore navigation, so we trigger the data fetch manually when it's the same url
    // Auth change will also trigger a fetch via useEffect in ValidationState
    if (
      !requiresAuth &&
      lastSearchParams?.feedUrl === autoDiscoveryUrlInput &&
      triggerDataFetch != undefined
    ) {
      triggerDataFetch();
      return;
    }
    navigate(
      `/gbfs-validator?AutoDiscoveryUrl=${encodeURIComponent(
        autoDiscoveryUrlInput,
      )}`,
    );
  };

  return (
    <Box
      id='input-box'
      sx={{
        padding: 2,
        pt: 3,
        marginTop: 2,
        backgroundColor: theme.palette.background.default,
        border: '3px solid ' + theme.palette.text.primary,
        borderRadius: '5px',
      }}
    >
      <Container
        id='input-box-header'
        component={'form'}
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          p: { xs: 0 },
        }}
      >
        <TextField
          variant='outlined'
          label='GBFS Auto-Discovery URL'
          placeholder='eg: https://example.com/gbfs.json'
          value={autoDiscoveryUrlInput ?? ''}
          sx={{ width: '100%', mr: 2 }}
          onChange={(e) => {
            setAutoDiscoveryUrlInput(e.target.value.trim());
          }}
          InputProps={{
            startAdornment: <SearchIcon sx={{ mr: 1 }}></SearchIcon>,
          }}
        />
        <Button
          variant='contained'
          color='primary'
          sx={{ p: '12px' }}
          disabled={isSubmitBoxDisabled()}
          type='submit'
          onClick={(e) => {
            e.preventDefault();
            validateGBFSFeed();
          }}
        >
          Validate
        </Button>
      </Container>
      <FormGroup>
        <FormControlLabel
          sx={{ width: 'fit-content' }}
          control={<Checkbox checked={requiresAuth} onChange={handleChange} />}
          label='Requires Authentication'
        />
        {requiresAuth && (
          <FormControl>
            <Select
              value={authType}
              onChange={handleAuthTypeChange}
              displayEmpty
              inputProps={{ 'aria-label': 'authentication type select' }}
            >
              <MenuItem value={''}>
                <em>Select Authentication Type</em>
              </MenuItem>
              <MenuItem value={AuthTypeEnum.BASIC}>Basic Auth</MenuItem>
              <MenuItem value={AuthTypeEnum.BEARER}>Bearer Token</MenuItem>
              <MenuItem value={AuthTypeEnum.OAUTH}>
                Oauth Client Credentials Grant
              </MenuItem>
            </Select>
          </FormControl>
        )}

        {requiresAuth && authType === AuthTypeEnum.BASIC && (
          <Box
            sx={{
              display: 'flex',
              gap: 2,
              mt: 2,
              flexWrap: { xs: 'wrap', md: 'nowrap' },
            }}
          >
            <TextField
              size='small'
              variant='outlined'
              label='Username'
              placeholder='Enter Username'
              value={basicAuthUsername ?? ''}
              fullWidth
              onChange={(e) => {
                setBasicAuthUsername(e.target.value);
              }}
            />
            <TextField
              size='small'
              variant='outlined'
              label='Password'
              placeholder='Enter Password'
              value={basicAuthPassword ?? ''}
              type='password'
              fullWidth
              onChange={(e) => {
                setBasicAuthPassword(e.target.value);
              }}
            />
          </Box>
        )}

        {requiresAuth && authType === AuthTypeEnum.BEARER && (
          <TextField
            size='small'
            variant='outlined'
            label='Token'
            placeholder='Enter Bearer Token'
            value={bearerAuthValue ?? ''}
            sx={{ mt: 2 }}
            fullWidth
            onChange={(e) => {
              setBearerAuthValue(e.target.value);
            }}
          />
        )}

        {requiresAuth && authType === AuthTypeEnum.OAUTH && (
          <Box
            sx={{
              display: 'flex',
              gap: 2,
              mt: 2,
              flexWrap: { xs: 'wrap', md: 'nowrap' },
            }}
          >
            <TextField
              size='small'
              variant='outlined'
              placeholder='Client Id'
              value={oauthClientId ?? ''}
              label='Client Id'
              fullWidth
              onChange={(e) => {
                setOauthClientId(e.target.value);
              }}
            />
            <TextField
              size='small'
              variant='outlined'
              placeholder='Enter Client Secret'
              label='Client Secret'
              fullWidth
              value={oauthClientSecret ?? ''}
              onChange={(e) => {
                setOauthClientSecret(e.target.value);
              }}
            />
            <TextField
              size='small'
              variant='outlined'
              placeholder='Enter Token Url'
              label='Token Url'
              fullWidth
              value={oauthTokenUrl ?? ''}
              onChange={(e) => {
                setOauthTokenUrl(e.target.value);
              }}
            />
          </Box>
        )}
      </FormGroup>
      <Box
        id='cta-buttons'
        sx={{
          display: 'flex',
          gap: { xs: 0, md: 2 },
          mt: 2,
          flexWrap: { xs: 'wrap', md: 'nowrap' },
        }}
      >
        <Button variant='text' color='primary' href='/feeds?gbfs=true'>
          Browse GBFS Feeds
        </Button>
        <Button variant='text' color='primary' href='/' endIcon={<OpenInNew />}>
          View GBFS Validator API Docs
        </Button>
      </Box>
    </Box>
  );
}
