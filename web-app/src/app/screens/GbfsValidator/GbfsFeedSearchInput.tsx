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
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthTypeEnum, useGbfsAuth } from '../../context/GbfsAuthProvider';

export default function GbfsFeedSearchInput(): React.ReactElement {
  const theme = useTheme();
  const navigate = useNavigate();
  const { setAuth } = useGbfsAuth();
  const [autoDiscoveryUrlInput, setAutoDiscoveryUrlInput] =
    useState<string>('');
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
