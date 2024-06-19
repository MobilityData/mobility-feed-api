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
import { selectIsAuthenticated } from '../store/selectors';
import LogoutConfirmModal from './LogoutConfirmModal';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { TreeView } from '@mui/x-tree-view/TreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import { OpenInNew } from '@mui/icons-material';
import '../styles/Header.css';
import { useRemoteConfig } from '../context/RemoteConfigProvider';
import i18n from '../../i18n';

const drawerWidth = 240;
const websiteTile = 'Mobility Database';
const DrawerContent: React.FC<{
  onLogoutClick: React.MouseEventHandler;
  onNavigationClick: (target: NavigationItem | string) => void;
  navigationItems: NavigationItem[];
}> = ({ onLogoutClick, onNavigationClick, navigationItems }) => {
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
        {isAuthenticated ? (
          <TreeView
            defaultCollapseIcon={<ExpandMoreIcon />}
            defaultExpandIcon={<ChevronRightIcon />}
            sx={{ textAlign: 'left' }}
          >
            <TreeItem nodeId='1' label='Account' sx={{ color: '#3959fa' }}>
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
            sx={{ color: '#3959fa' }}
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
  const { config } = useRemoteConfig();

  React.useEffect(() => {
    setNavigationItems(buildNavigationItems(config));
  }, [config]);

  const navigateTo = useNavigate();
  const isAuthenticated = useSelector(selectIsAuthenticated);

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

  const handleMenuItemClick = (item: NavigationItem): void => {
    handleMenuClose();
    handleNavigation(item);
  };

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
              }}
              className='btn-link'
            >
              <Avatar src='/assets/MOBILTYDATA_logo_purple_M.png'></Avatar>
              <Typography
                variant='h5'
                component='div'
                className='website-title'
                sx={{
                  flexGrow: 1,
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
                key={item.title}
                sx={{ color: item.color, minWidth: 'fit-content' }}
                onClick={() => {
                  handleNavigation(item);
                }}
                variant={'text'}
                endIcon={item.external === true ? <OpenInNew /> : null}
              >
                {item.title}
              </Button>
            ))}
            {isAuthenticated ? (
              <>
                <Button
                  aria-controls='account-menu'
                  aria-haspopup='true'
                  onClick={handleMenuOpen}
                  endIcon={<ArrowDropDownIcon />}
                >
                  Account
                </Button>
                <Menu
                  id='account-menu'
                  anchorEl={anchorEl}
                  open={Boolean(anchorEl)}
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
            {config.enableLanguageToggle && (
              <Select
                value={i18n.language}
                onChange={(lang) => {
                  void i18n.changeLanguage(lang.target.value);
                }}
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
