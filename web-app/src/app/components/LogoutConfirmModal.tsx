import {
  Box,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  Dialog,
} from '@mui/material';
import React from 'react';
import { useAppDispatch } from '../hooks';
import { logout } from '../store/profile-reducer';
import { SIGN_IN_TARGET } from '../constants/Navigation';
import { useNavigate } from 'react-router-dom';

interface ConfirmModalProps {
  openDialog: boolean;
  setOpenDialog: (value: boolean) => void;
}

export default function ConfirmModal({
  openDialog,
  setOpenDialog,
}: ConfirmModalProps): React.ReactElement {
  const dispatch = useAppDispatch();
  const navigateTo = useNavigate();
  const confirmLogout = (): void => {
    dispatch(logout({ redirectScreen: SIGN_IN_TARGET, navigateTo }));
    setOpenDialog(false);
  };

  return (
    <Box sx={{ display: 'flex' }}>
      <Dialog open={openDialog}>
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
  );
}
