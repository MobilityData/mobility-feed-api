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
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import LogoutIcon from '@mui/icons-material/Logout';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import HelpIcon from '@mui/icons-material/Help';
import {
  type NavigationHandler,
  navigationItems,
  navigationAccountItem,
  navigationHelpItem,
  SIGN_IN_TARGET,
} from '../constants/Navigation';
import type NavigationItem from '../interface/Navigation';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { selectIsAuthenticated } from '../store/selectors';
import LogoutConfirmModal from './LogoutConfirmModal';
import { OpenInNew } from '@mui/icons-material';
import '../styles/Header.css';

const drawerWidth = 240;
const websiteTile = 'Mobility Database';

const DrawerContent: React.FC<{
  onClick: React.MouseEventHandler;
  onNavigationClick: NavigationHandler;
}> = ({ onClick, onNavigationClick }) => {
  return (
    <Box onClick={onClick} sx={{ textAlign: 'center' }}>
      <Typography
        variant='h6'
        sx={{ my: 2 }}
        data-testid='websiteTile'
        className='website-title'
      >
        {websiteTile}
      </Typography>
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
            <ListItemButton sx={{ textAlign: 'center' }}>
              <ListItemText>{item.title}</ListItemText>
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Box>
  );
};

export default function DrawerAppBar(): React.ReactElement {
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [openDialog, setOpenDialog] = React.useState(false);

  const navigateTo = useNavigate();
  const isAuthenticated = useSelector(selectIsAuthenticated);

  const handleDrawerToggle = (): void => {
    setMobileOpen((prevState) => !prevState);
  };

  const handleNavigation = (navigationItem: NavigationItem): void => {
    navigateTo(navigationItem.target);
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
          <a
            href={'/'}
            style={{
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
            }}
            className='btn-link'
          >
            <IconButton
              color='inherit'
              aria-label='open drawer'
              edge='start'
              onClick={handleDrawerToggle}
              sx={{ mr: 2, display: { md: 'none' } }}
            >
              <MenuIcon />
            </IconButton>

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

          <Box sx={{ display: { xs: 'none', md: 'block' } }}>
            {navigationItems.map((item) => (
              <Button
                key={item.title}
                sx={{ color: item.color, minWidth: 'fit-content' }}
                onClick={() => {
                  handleNavigation(item);
                }}
                variant={item.variant}
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
                  <MenuItem
                    onClick={() => {
                      handleMenuItemClick(navigationHelpItem);
                    }}
                  >
                    <ListItemIcon>
                      <HelpIcon fontSize='small' />
                    </ListItemIcon>
                    Help
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
            onClick={handleDrawerToggle}
            onNavigationClick={handleNavigation}
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
