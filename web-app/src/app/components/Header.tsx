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
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import {
  type NavigationHandler,
  SIGN_IN_TARGET,
  SIGN_OUT_TARGET,
  navigationItems,
} from '../constants/Navigation';
import type NavigationItem from '../interface/Navigation';
import { useNavigate } from 'react-router-dom';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import { useSelector } from 'react-redux';
import { logout } from '../store/profile-reducer';
import { useAppDispatch } from '../hooks';
import { selectIsAuthenticated } from '../store/selectors';

const drawerWidth = 240;
const websiteTile = 'Mobility Database';

const DrawerContent: React.FC<{
  onClick: React.MouseEventHandler;
  onNavigationClick: NavigationHandler;
}> = ({ onClick, onNavigationClick }) => {
  const isAuthenticated = useSelector(selectIsAuthenticated);
  return (
    <Box onClick={onClick} sx={{ textAlign: 'center' }}>
      <Typography variant='h6' sx={{ my: 2 }} data-testid='websiteTile'>
        {websiteTile}
      </Typography>
      <Divider />
      <List>
        {navigationItems(isAuthenticated).map((item) => (
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
  const dispatch = useAppDispatch();

  const handleDrawerToggle = (): void => {
    setMobileOpen((prevState) => !prevState);
  };

  const handleNavigation = (navigationItem: NavigationItem): void => {
    if (navigationItem.target === SIGN_OUT_TARGET) {
      setOpenDialog(true);
    } else {
      navigateTo(navigationItem.target);
    }
  };

  const confirmLogout = (): void => {
    dispatch(logout({ redirectScreen: SIGN_IN_TARGET, navigateTo }));
    setOpenDialog(false);
  };

  const container =
    window !== undefined ? () => window.document.body : undefined;

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar component='nav' color='inherit' elevation={0}>
        <Toolbar>
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
            sx={{ flexGrow: 1, display: { xs: 'none', md: 'block' } }}
          >
            {websiteTile}
          </Typography>
          <Box sx={{ display: { xs: 'none', md: 'block' } }}>
            {navigationItems(isAuthenticated).map((item) => (
              <Button
                key={item.title}
                sx={{ color: item.color }}
                onClick={() => {
                  handleNavigation(item);
                }}
                variant={item.variant}
              >
                {item.title}
              </Button>
            ))}
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
      <Box sx={{ display: 'flex' }}>
        {/* ... (the rest of your JSX) */}
        <Dialog
          open={openDialog}
          onClose={() => {
            setOpenDialog(false);
          }}
        >
          <DialogTitle color='primary' sx={{ fontWeight: 'bold' }}>
            Confirm Sign Out
          </DialogTitle>
          <DialogContent dividers>
            <DialogContentText color='inherit'>
              Are you sure you want to sign out?
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button
              onClick={() => {
                setOpenDialog(false);
              }}
              color='inherit'
              variant='outlined'
            >
              Cancel
            </Button>
            <Button onClick={confirmLogout} color='primary' variant='contained'>
              Confirm
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Box>
  );
}
