import * as React from 'react';
import {
  AppBar,
  Box,
  Divider,
  Avatar,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Toolbar,
  Typography,
  Button,
  ListItemIcon,
  Menu,
  MenuItem,
  Select,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import LogoutIcon from '@mui/icons-material/Logout';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import {
  navigationAccountItem,
  SIGN_IN_TARGET,
  ACCOUNT_TARGET,
  buildNavigationItems,
} from '../constants/Navigation';
import type NavigationItem from '../interface/Navigation';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { selectIsAuthenticated, selectUserEmail } from '../store/selectors';
import LogoutConfirmModal from './LogoutConfirmModal';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { TreeView } from '@mui/x-tree-view/TreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import { BikeScooterOutlined, OpenInNew } from '@mui/icons-material';
import '../styles/Header.css';
import { useRemoteConfig } from '../context/RemoteConfigProvider';
import i18n from '../../i18n';
import { NestedMenuItem } from 'mui-nested-menu';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import { theme } from '../Theme';

const drawerWidth = 240;
const websiteTile = 'Mobility Database';
const DrawerContent: React.FC<{
  onLogoutClick: React.MouseEventHandler;
  onNavigationClick: (target: NavigationItem | string) => void;
  navigationItems: NavigationItem[];
  metricsOptionsEnabled: boolean;
}> = ({
  onLogoutClick,
  onNavigationClick,
  navigationItems,
  metricsOptionsEnabled,
}) => {
  const isAuthenticated = useSelector(selectIsAuthenticated);
  const navigateTo = useNavigate();
  return (
    <Box>
      <Box
        sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}
        onClick={() => {
          navigateTo('/');
        }}
      >
        <Avatar src='/assets/MOBILTYDATA_logo_purple_M.png'></Avatar>
        <Typography
          variant='h6'
          sx={{ my: 2, cursor: 'pointer' }}
          data-testid='websiteTile'
        >
          {websiteTile}
        </Typography>
      </Box>
      <Divider />
      <List>
        {navigationItems.map((item) => (
          <ListItem
            key={item.title}
            disablePadding
            onClick={() => {
              onNavigationClick(item);
            }}
          >
            <ListItemButton
              sx={{
                textAlign: 'left',
                p: 0,
                pl: '16px',
              }}
            >
              <ListItemText>
                {item.title}{' '}
                {item.external === true ? (
                  <OpenInNew sx={{ verticalAlign: 'middle' }} />
                ) : null}
              </ListItemText>
            </ListItemButton>
          </ListItem>
        ))}
        <Divider sx={{ mt: 2, mb: 2 }} />
        {metricsOptionsEnabled && (
          <TreeView
            defaultCollapseIcon={<ExpandMoreIcon />}
            defaultExpandIcon={<ChevronRightIcon />}
            sx={{ textAlign: 'left' }}
          >
            <TreeItem
              nodeId='1'
              label='GTFS Metrics'
              sx={{ color: theme.palette.primary.main }}
            >
              <TreeItem
                nodeId='2'
                label='Feeds'
                sx={{ color: '#7c7c7c', cursor: 'pointer' }}
                onClick={() => {
                  onNavigationClick('/metrics/gtfs/feeds');
                }}
              />
              <TreeItem
                nodeId='3'
                label='Notices'
                sx={{ color: '#7c7c7c', cursor: 'pointer' }}
                onClick={() => {
                  onNavigationClick('/metrics/gtfs/notices');
                }}
              />
              <TreeItem
                nodeId='4'
                label='Features'
                sx={{ color: '#7c7c7c', cursor: 'pointer' }}
                onClick={() => {
                  onNavigationClick('/metrics/gtfs/features');
                }}
              />
            </TreeItem>
            <TreeItem
              nodeId='5'
              label='GBFS Metrics'
              sx={{ color: theme.palette.primary.main }}
            >
              <TreeItem
                nodeId='6'
                label='Feeds'
                sx={{ color: '#7c7c7c', cursor: 'pointer' }}
                onClick={() => {
                  onNavigationClick('/metrics/gbfs/feeds');
                }}
              />
              <TreeItem
                nodeId='7'
                label='Notices'
                sx={{ color: '#7c7c7c', cursor: 'pointer' }}
                onClick={() => {
                  onNavigationClick('/metrics/gbfs/notices');
                }}
              />
              <TreeItem
                nodeId='8'
                label='Versions'
                sx={{ color: '#7c7c7c', cursor: 'pointer' }}
                onClick={() => {
                  onNavigationClick('/metrics/gbfs/versions');
                }}
              />
            </TreeItem>
          </TreeView>
        )}

        {isAuthenticated ? (
          <TreeView
            defaultCollapseIcon={<ExpandMoreIcon />}
            defaultExpandIcon={<ChevronRightIcon />}
            sx={{ textAlign: 'left' }}
          >
            <TreeItem
              nodeId='1'
              label='Account'
              sx={{ color: theme.palette.primary.main }}
              data-cy='accountHeader'
            >
              <TreeItem
                nodeId='2'
                label='Account Details'
                sx={{ color: '#7c7c7c', cursor: 'pointer' }}
                onClick={() => {
                  onNavigationClick(ACCOUNT_TARGET);
                }}
                icon={<AccountCircleIcon fontSize='small' />}
              />
              <TreeItem
                nodeId='4'
                label='Sign Out'
                sx={{ color: '#7c7c7c' }}
                onClick={onLogoutClick}
                icon={<LogoutIcon fontSize='small' />}
              />
            </TreeItem>
          </TreeView>
        ) : (
          <ListItem
            sx={{ color: theme.palette.primary.main }}
            onClick={() => {
              onNavigationClick(SIGN_IN_TARGET);
            }}
            key={'Login'}
            disablePadding
          >
            <ListItemButton
              sx={{
                textAlign: 'left',
                p: 0,
                pl: '16px',
              }}
            >
              <ListItemText>Login</ListItemText>
            </ListItemButton>
          </ListItem>
        )}
      </List>
    </Box>
  );
};

export default function DrawerAppBar(): React.ReactElement {
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [openDialog, setOpenDialog] = React.useState(false);
  const [navigationItems, setNavigationItems] = React.useState<
    NavigationItem[]
  >([]);
  const [currentLanguage, setCurrentLanguage] = React.useState<
    string | undefined
  >(i18n.language);
  const { config } = useRemoteConfig();

  i18n.on('languageChanged', (lang) => {
    setCurrentLanguage(i18n.language);
  });

  React.useEffect(() => {
    setNavigationItems(buildNavigationItems(config));
  }, [config]);

  const navigateTo = useNavigate();
  const isAuthenticated = useSelector(selectIsAuthenticated);
  const userEmail = useSelector(selectUserEmail);

  const handleDrawerToggle = (): void => {
    setMobileOpen((prevState) => !prevState);
  };

  const handleNavigation = (navigationItem: NavigationItem | string): void => {
    if (typeof navigationItem === 'string') navigateTo(navigationItem);
    else {
      if (navigationItem.external === true)
        window.open(navigationItem.target, '_blank', 'noopener noreferrer');
      else navigateTo(navigationItem.target);
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

  const metricsOptionsEnabled =
    config.enableMetrics || userEmail?.endsWith('mobilitydata.org') === true;

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        component='nav'
        color='inherit'
        elevation={0}
        sx={{ background: 'white' }}
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
              <Avatar src='/assets/MOBILTYDATA_logo_purple_M.png'></Avatar>
              <Typography
                variant='h5'
                component='div'
                className='website-title'
                sx={{
                  display: { xs: 'none', md: 'block' },
                }}
              >
                {websiteTile}
              </Typography>
            </a>
          </Box>

          <Box sx={{ display: { xs: 'none', md: 'block' } }}>
            {navigationItems.map((item) => (
              <Button
                href={item.external === true ? item.target : '/' + item.target}
                key={item.title}
                sx={{ color: item.color, minWidth: 'fit-content', mx: 1 }}
                target={item.external === true ? '_blank' : '_self'}
                rel={item.external === true ? 'noopener noreferrer' : ''}
                variant={'text'}
                endIcon={item.external === true ? <OpenInNew /> : null}
              >
                {item.title}
              </Button>
            ))}
            {/* Allow users with mobilitydata.org email to access metrics */}
            {metricsOptionsEnabled && (
              <>
                <Button
                  aria-controls='analytics-menu'
                  aria-haspopup='true'
                  endIcon={<ArrowDropDownIcon />}
                  onClick={handleMenuOpen}
                  sx={{ color: 'black' }}
                  id='analytics-button-menu'
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
                    <MenuItem
                      onClick={() => {
                        handleMenuItemClick('/metrics/gtfs/feeds');
                      }}
                    >
                      Feeds
                    </MenuItem>
                    <MenuItem
                      onClick={() => {
                        handleMenuItemClick('/metrics/gtfs/notices');
                      }}
                    >
                      Notices
                    </MenuItem>
                    <MenuItem
                      onClick={() => {
                        handleMenuItemClick('/metrics/gtfs/features');
                      }}
                    >
                      Features
                    </MenuItem>
                  </NestedMenuItem>
                  <NestedMenuItem
                    label='GBFS'
                    parentMenuOpen={Boolean(anchorEl)}
                    leftIcon={<BikeScooterOutlined />}
                  >
                    <MenuItem
                      onClick={() => {
                        handleMenuItemClick('/metrics/gbfs/feeds');
                      }}
                    >
                      Feeds
                    </MenuItem>
                    <MenuItem
                      onClick={() => {
                        handleMenuItemClick('/metrics/gbfs/notices');
                      }}
                    >
                      Notices
                    </MenuItem>
                    <MenuItem
                      onClick={() => {
                        handleMenuItemClick('/metrics/gbfs/versions');
                      }}
                    >
                      Versions
                    </MenuItem>
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
                      <AccountCircleIcon fontSize='small' />
                    </ListItemIcon>
                    Account Details
                  </MenuItem>
                  <MenuItem onClick={handleLogoutClick}>
                    <ListItemIcon>
                      <LogoutIcon fontSize='small' />
                    </ListItemIcon>
                    Sign Out
                  </MenuItem>
                </Menu>
              </>
            ) : (
              <Button href={SIGN_IN_TARGET}>Login</Button>
            )}
            {/* Testing language tool */}
            {config.enableLanguageToggle && currentLanguage !== undefined && (
              <Select
                value={currentLanguage}
                onChange={(lang) => {
                  void i18n.changeLanguage(lang.target.value);
                }}
                variant='standard'
              >
                <MenuItem value={'en'}>EN</MenuItem>
                <MenuItem value={'fr'}>FR</MenuItem>
              </Select>
            )}
          </Box>
        </Toolbar>
      </AppBar>
      <nav>
        <Drawer
          container={container}
          variant='temporary'
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: drawerWidth,
            },
          }}
        >
          <DrawerContent
            onLogoutClick={handleLogoutClick}
            onNavigationClick={handleNavigation}
            navigationItems={navigationItems}
            metricsOptionsEnabled={metricsOptionsEnabled}
          />
        </Drawer>
      </nav>
      <LogoutConfirmModal
        openDialog={openDialog}
        setOpenDialog={setOpenDialog}
      />
    </Box>
  );
}
