'use client';

import * as React from 'react';
import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  Toolbar,
  Typography,
  Button,
  ListItemIcon,
  Menu,
  MenuItem,
  Select,
  useTheme,
  Link,
  Alert,
  AlertTitle,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import LogoutIcon from '@mui/icons-material/Logout';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import {
  navigationAccountItem,
  SIGN_IN_TARGET,
  buildNavigationItems,
  gtfsMetricsNavItems,
  gbfsMetricsNavItems,
} from '../constants/Navigation';
import type NavigationItem from '../interface/Navigation';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import LogoutConfirmModal from './LogoutConfirmModal';
import { BikeScooterOutlined, OpenInNew } from '@mui/icons-material';
import { useRemoteConfig } from '../context/RemoteConfigProvider';
import { NestedMenuItem } from 'mui-nested-menu';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import DepartureBoardIcon from '@mui/icons-material/DepartureBoard';
import { fontFamily } from '../Theme';
import { defaultRemoteConfigValues } from '../interface/RemoteConfig';
import { animatedButtonStyling } from './Header.style';
import DrawerContent from './HeaderMobileDrawer';
import ThemeToggle from './ThemeToggle';
import { useTranslations, useLocale } from 'next-intl';

export default function DrawerAppBar(): React.ReactElement {
  const searchParams = useSearchParams();
  const hasTransitFeedsRedirectParam =
    searchParams.get('utm_source') === 'transitfeeds';
  const theme = useTheme();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [hasTransitFeedsRedirect, setHasTransitFeedsRedirect] = React.useState(
    hasTransitFeedsRedirectParam,
  );
  const [openDialog, setOpenDialog] = React.useState(false);
  const [activeTab, setActiveTab] = React.useState('');
  const [navigationItems, setNavigationItems] = React.useState<
    NavigationItem[]
  >(buildNavigationItems(defaultRemoteConfigValues));
  const locale = useLocale();
  const { config } = useRemoteConfig();
  const t = useTranslations('common');

  React.useEffect(() => {
    setActiveTab(pathname ?? '');
  }, [pathname]);

  React.useEffect(() => {
    setNavigationItems(buildNavigationItems(config));
  }, [config]);

  const router = useRouter();
  const isAuthenticated = true; // useSelector(selectIsAuthenticated);
  //const userEmail = useSelector(selectUserEmail);

  const handleDrawerToggle = (): void => {
    setMobileOpen((prevState) => !prevState);
  };

  const handleNavigation = (navigationItem: NavigationItem | string): void => {
    if (typeof navigationItem === 'string') router.push(navigationItem);
    else {
      if (navigationItem.external === true)
        window.open(navigationItem.target, '_blank', 'noopener noreferrer');
      else router.push(navigationItem.target);
    }
    setMobileOpen(false);
  };

  const handleLogoutClick = (): void => {
    setOpenDialog(true);
    handleMenuClose();
  };

  const container =
    window !== undefined ? () => window.document.body : undefined;

  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>): void => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = (): void => {
    setAnchorEl(null);
  };

  const handleMenuItemClick = (item: NavigationItem | string): void => {
    handleMenuClose();
    handleNavigation(item);
  };

  const metricsOptionsEnabled = false;
  //config.enableMetrics || userEmail?.endsWith('mobilitydata.org') === true;

  return (
    <Box
      sx={{
        display: 'flex',
        height: hasTransitFeedsRedirect ? '115px' : '64px',
        mb: { xs: 2, md: 4 },
      }}
    >
      <AppBar
        component='nav'
        color='inherit'
        elevation={0}
        sx={{
          background: theme.palette.background.paper,
          fontFamily: fontFamily.secondary,
          borderBottom: '1px solid',
          borderColor: theme.palette.divider,
        }}
      >
        <Toolbar sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <IconButton
              color='inherit'
              aria-label='open drawer'
              edge='start'
              onClick={handleDrawerToggle}
              sx={{ mr: 2, display: { md: 'none' } }}
            >
              <MenuIcon />
            </IconButton>
            <a
              href={'/'}
              style={{
                textDecoration: 'none',
                display: 'flex',
                alignItems: 'center',
              }}
              className='btn-link'
            >
              <picture style={{ display: 'flex' }}>
                <source
                  media='(min-width: 50px)'
                  srcSet='/assets/MOBILTYDATA_logo_purple_M.webp'
                  width='50'
                  height='50'
                />
                <source
                  src='/assets/MOBILTYDATA_logo_purple_M.png'
                  type='image/png'
                />
                <img
                  alt='MobilityData logo'
                  src='/assets/MOBILTYDATA_logo_purple_M.png'
                />
              </picture>
              <Typography
                variant='h5'
                component='h1'
                color={'primary'}
                sx={{
                  ml: 1,
                  fontWeight: 700,
                  display: { xs: 'none', md: 'block' },
                }}
              >
                Mobility Database
              </Typography>
            </a>
          </Box>

          <Box sx={{ display: { xs: 'none', md: 'block' } }}>
            {navigationItems.map((item) => (
              <Button
                sx={(theme) => ({
                  ...animatedButtonStyling(theme),
                  color: theme.palette.text.primary,
                })}
                href={item.external === true ? item.target : '/' + item.target}
                key={item.title}
                target={item.external === true ? '_blank' : '_self'}
                rel={item.external === true ? 'noopener noreferrer' : ''}
                variant={'text'}
                endIcon={item.external === true ? <OpenInNew /> : null}
                className={
                  activeTab.includes('/' + item.target) ? 'active' : ''
                }
              >
                {item.title}
              </Button>
            ))}
            {config.gbfsValidator && (
              <>
                <Button
                  aria-controls='validator-menu'
                  aria-haspopup='true'
                  endIcon={<ArrowDropDownIcon />}
                  onClick={handleMenuOpen}
                  sx={(theme) => ({
                    ...animatedButtonStyling(theme),
                    color: theme.palette.text.primary,
                  })}
                  id='validator-button-menu'
                  className={
                    activeTab.includes('validator') ? 'active short' : ''
                  }
                >
                  {t('validators')}
                </Button>
                <Menu
                  id='validator-menu'
                  anchorEl={anchorEl}
                  open={
                    anchorEl !== null && anchorEl.id === 'validator-button-menu'
                  }
                  onClose={handleMenuClose}
                >
                  <MenuItem
                    key={'gbfs-validator'}
                    onClick={() => {
                      handleMenuItemClick('gbfs-validator');
                    }}
                    sx={{ display: 'flex', gap: 1 }}
                  >
                    <BikeScooterOutlined fontSize='small' />
                    {t('gbfsValidator')}
                  </MenuItem>
                  <MenuItem
                    key={'gtfs-validator'}
                    component={Link}
                    href='https://gtfs-validator.mobilitydata.org/'
                    target='_blank'
                    rel='noopener noreferrer'
                  >
                    <DirectionsBusIcon fontSize='small' sx={{ mr: 1 }} />
                    {t('gtfsValidator')}
                    <OpenInNew fontSize='small' sx={{ ml: 0.5 }} />
                  </MenuItem>
                  <MenuItem
                    key={'gtfs-rt-validator'}
                    component={Link}
                    href='https://github.com/MobilityData/gtfs-realtime-validator'
                    target='_blank'
                    rel='noopener noreferrer'
                  >
                    <DepartureBoardIcon fontSize='small' sx={{ mr: 1 }} />
                    {t('gtfsRtValidator')}
                    <OpenInNew fontSize='small' sx={{ ml: 0.5 }} />
                  </MenuItem>
                </Menu>
              </>
            )}
            {/* Allow users with mobilitydata.org email to access metrics */}
            {metricsOptionsEnabled && (
              <>
                <Button
                  aria-controls='analytics-menu'
                  aria-haspopup='true'
                  endIcon={<ArrowDropDownIcon />}
                  onClick={handleMenuOpen}
                  sx={(theme) => ({
                    ...animatedButtonStyling(theme),
                    color: theme.palette.text.primary,
                  })}
                  id='analytics-button-menu'
                  className={
                    activeTab.includes('metrics') ? 'active short' : ''
                  }
                >
                  Metrics
                </Button>
                <Menu
                  id='analytics-menu'
                  anchorEl={anchorEl}
                  open={
                    anchorEl !== null && anchorEl.id === 'analytics-button-menu'
                  }
                  onClose={handleMenuClose}
                >
                  <NestedMenuItem
                    label='GTFS'
                    parentMenuOpen={Boolean(anchorEl)}
                    leftIcon={<DirectionsBusIcon />}
                  >
                    {gtfsMetricsNavItems.map((item) => (
                      <MenuItem
                        key={item.title}
                        onClick={() => {
                          handleMenuItemClick(item.target);
                        }}
                      >
                        {item.title}
                      </MenuItem>
                    ))}
                  </NestedMenuItem>
                  <NestedMenuItem
                    label='GBFS'
                    parentMenuOpen={Boolean(anchorEl)}
                    leftIcon={<BikeScooterOutlined />}
                  >
                    {gbfsMetricsNavItems.map((item) => (
                      <MenuItem
                        key={item.title}
                        onClick={() => {
                          handleMenuItemClick(item.target);
                        }}
                      >
                        {item.title}
                      </MenuItem>
                    ))}
                  </NestedMenuItem>
                </Menu>
              </>
            )}

            {isAuthenticated ? (
              <>
                <Button
                  aria-controls='account-menu'
                  aria-haspopup='true'
                  onClick={handleMenuOpen}
                  endIcon={<ArrowDropDownIcon />}
                  id='account-button-menu'
                  sx={animatedButtonStyling}
                  className={activeTab === '/account' ? 'active short' : ''}
                  data-cy='accountHeader'
                >
                  Account
                </Button>
                <Menu
                  id='account-menu'
                  anchorEl={anchorEl}
                  open={
                    anchorEl !== null && anchorEl.id === 'account-button-menu'
                  }
                  onClose={handleMenuClose}
                >
                  <MenuItem
                    onClick={() => {
                      handleMenuItemClick(navigationAccountItem);
                    }}
                  >
                    <ListItemIcon>
                      <AccountCircleIcon
                        fontSize='small'
                        sx={{ color: theme.palette.text.primary }}
                      />
                    </ListItemIcon>
                    Account Details
                  </MenuItem>
                  <MenuItem onClick={handleLogoutClick}>
                    <ListItemIcon>
                      <LogoutIcon
                        fontSize='small'
                        sx={{ color: theme.palette.text.primary }}
                      />
                    </ListItemIcon>
                    Sign Out
                  </MenuItem>
                </Menu>
              </>
            ) : (
              <Button
                sx={{ fontFamily: fontFamily.secondary }}
                href={SIGN_IN_TARGET}
              >
                Login
              </Button>
            )}
            <ThemeToggle></ThemeToggle>
            {/* Testing language tool -> to revisit */}
            {config.enableLanguageToggle && (
              <Select
                value={locale}
                onChange={(e) => {
                  const newLocale = e.target.value;
                  const currentHost = window.location.host;
                  const currentProtocol = window.location.protocol;
                  const currentPath =
                    window.location.pathname + window.location.search;

                  let newHost = currentHost;
                  if (newLocale === 'fr') {
                    if (!currentHost.startsWith('fr.')) {
                      newHost = 'fr.' + currentHost;
                    }
                  } else {
                    if (currentHost.startsWith('fr.')) {
                      newHost = currentHost.replace('fr.', '');
                    }
                  }

                  if (newHost !== currentHost) {
                    window.location.href = `${currentProtocol}//${newHost}${currentPath}`;
                  }
                }}
                variant='standard'
                inputProps={{ 'aria-label': 'language select' }}
              >
                <MenuItem value={'en'}>EN</MenuItem>
                <MenuItem value={'fr'}>FR</MenuItem>
              </Select>
            )}
          </Box>
        </Toolbar>
        {hasTransitFeedsRedirect && (
          <Alert
            severity='warning'
            onClose={() => {
              setHasTransitFeedsRedirect(false);
              if (hasTransitFeedsRedirectParam) {
                // Remove utm_source from URL
                const newSearchParams = new URLSearchParams(searchParams);
                newSearchParams.delete('utm_source');
                const newPath = `${pathname}?${newSearchParams.toString()}`;
                router.replace(newPath);
              }
            }}
            sx={{ '.MuiAlert-message': { pb: { xs: 0, md: 1 } } }}
          >
            <AlertTitle>
              You&apos;ve been redirected from TransitFeeds
            </AlertTitle>
            <Box
              component={'span'}
              sx={{ display: { xs: 'none', md: 'block' } }}
            >
              This page now lives on MobilityDatabase.org, where you&apos;ll
              find the most up-to-date transit data.
            </Box>
          </Alert>
        )}
      </AppBar>

      <nav>
        {/* <Drawer
          container={container}
          variant='temporary'
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: '240px',
            },
          }}
        >
          <DrawerContent
            onLogoutClick={handleLogoutClick}
            navigationItems={navigationItems}
            metricsOptionsEnabled={metricsOptionsEnabled}
          />
        </Drawer> */}
      </nav>
      <LogoutConfirmModal
        openDialog={openDialog}
        setOpenDialog={setOpenDialog}
      />
    </Box>
  );
}
