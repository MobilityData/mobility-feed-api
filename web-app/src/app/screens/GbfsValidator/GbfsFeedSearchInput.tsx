import { OpenInNew } from '@mui/icons-material';
import {
  Box,
  TextField,
  Button,
  FormGroup,
  FormControlLabel,
  Checkbox,
  useTheme,
  Link,
  Container,
  FormControl,
  MenuItem,
  Select,
  type SelectChangeEvent,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { useState } from 'react';

enum AuthTypeEnum {
  BASIC = 'Basic Auth',
  BEARER = 'Bearer Token',
  OAUTH = 'Oauth Client Credentials Grant',
  CUSTOM = 'Custom Headers (e.g. API Key)',
}

export default function GbfsFeedSearchInput(): React.ReactElement {
  const theme = useTheme();
  const [autoDiscoveryUrlInput, setAutoDiscoveryUrlInput] =
    useState<string>('');
  const [requiresAuth, setRequiresAuth] = useState(false);
  const [authType, setAuthType] = useState<string>('');
  const [basicAuthUsername, setBasicAuthUsername] = useState<string>('');
  const [basicAuthPassword, setBasicAuthPassword] = useState<string>('');
  const [bearerAuthValue, setBearerAuthValue] = useState<string>('');
  const [oauthClientId, setOauthClientId] = useState<string>('');
  const [oauthClientSecret, setOauthClientSecret] = useState<string>('');
  const [oauthTokenUrl, setOauthTokenUrl] = useState<string>('');

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
    setRequiresAuth(event.target.checked);
  };

  const handleAuthTypeChange = (event: SelectChangeEvent<string>): void => {
    setAuthType(event.target.value);
    setBasicAuthUsername('');
    setBasicAuthPassword('');
    setBearerAuthValue('');
    setOauthClientId('');
    setOauthClientSecret('');
    setOauthTokenUrl('');
  };

  const isSubmitBoxDisabled = (): boolean => {
    if (autoDiscoveryUrlInput === '') return true;
    if (requiresAuth) {
      if (authType === '') return true;
      if (authType === AuthTypeEnum.BASIC) {
        if (basicAuthUsername === '' || basicAuthPassword === '') return true;
      }
      if (authType === AuthTypeEnum.BEARER) {
        if (bearerAuthValue === '') return true;
      }
      if (authType === AuthTypeEnum.OAUTH) {
        if (
          oauthClientId === '' ||
          oauthClientSecret === '' ||
          oauthTokenUrl === ''
        )
          return true;
      }
    }
    return false;
  };

  const validateGBFSFeed = (): void => {
    // 1. dispatch action with url and auth details (state -> loading)
    // once done then
    // 2. navigate to /gbfs-validator?AutoDiscoveryUrl=url
    // or
    // navigate to /gbfs-validator?AutoDiscoveryUrl=url&auth details
    // store the auth details in context
    // let the GbfsValidator component handle the loading state
  };

  return (
    <Box
      id='input-box'
      sx={{
        padding: 2,
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
          placeholder='eg: https://example.com/gbfs.json'
          sx={{ width: '100%', mr: 2 }}
          onChange={(e) => {
            setAutoDiscoveryUrlInput(e.target.value);
          }}
          InputProps={{
            startAdornment: <SearchIcon sx={{ mr: 1 }}></SearchIcon>,
          }}
        />
        <Button
          variant='contained'
          color='primary'
          sx={{ p: '12px' }}
          component={Link}
          href={`/gbfs-validator?AutoDiscoveryUrl=${encodeURIComponent(
            autoDiscoveryUrlInput,
          )}`}
          disabled={isSubmitBoxDisabled()}
          type='submit'
          onClick={() => {
            validateGBFSFeed();
          }}
        >
          Validate
        </Button>
      </Container>
      <FormGroup>
        <FormControlLabel
          control={<Checkbox checked={requiresAuth} onChange={handleChange} />}
          label='Requires Authentication'
        />
        {requiresAuth && (
          <FormControl>
            <Select
              value={authType}
              onChange={handleAuthTypeChange}
              displayEmpty
              inputProps={{ 'aria-label': 'Without label' }}
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
          <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
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
          <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
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
      <Box id='cta-buttons' sx={{ display: 'flex', gap: 2, mt: 2 }}>
        <Button variant='text' color='primary'>
          Broswe GBFS Feeds
        </Button>
        <Button variant='text' color='primary' endIcon={<OpenInNew />}>
          View GBFS Validator API Docs
        </Button>
      </Box>
    </Box>
  );
}
