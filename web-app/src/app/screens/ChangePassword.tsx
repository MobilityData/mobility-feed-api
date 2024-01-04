import * as React from 'react';
import Button from '@mui/material/Button';
import CssBaseline from '@mui/material/CssBaseline';
import TextField from '@mui/material/TextField';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import { useFormik } from 'formik';
import * as Yup from 'yup';
import {
  Alert,
  IconButton,
  InputAdornment,
  Tooltip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
} from '@mui/material';
import {
  passwordValidationRegex,
  passwordValidationError,
} from '../constants/Validation';
import { useAppDispatch } from '../hooks';
import { changePassword, changePasswordInit } from '../store/profile-reducer';
import {
  selectChangePasswordError,
  selectChangePasswordStatus,
} from '../store/profile-selectors';
import { useSelector } from 'react-redux/es/hooks/useSelector';
import { useNavigate } from 'react-router-dom';
import { VisibilityOffOutlined, VisibilityOutlined } from '@mui/icons-material';

export default function ChangePassword(): React.ReactElement {
  const dispatch = useAppDispatch();
  const navigateTo = useNavigate();
  const changePasswordError = useSelector(selectChangePasswordError);
  const changePasswordStatus = useSelector(selectChangePasswordStatus);
  const ChangePasswordSchema = Yup.object().shape({
    currentPassword: Yup.string().required('Password is required'),
    newPassword: Yup.string()
      .required('New Password is required')
      .min(12, 'Password is too short - should be 12 chars minimum')
      .matches(passwordValidationRegex, 'Password error'),
    confirmNewPassword: Yup.string()
      .required('Confirm New Password is required')
      .matches(passwordValidationRegex, 'Password error')
      .oneOf([Yup.ref('newPassword')], 'Passwords must match'),
  });

  const formik = useFormik({
    initialValues: {
      currentPassword: '',
      newPassword: '',
      confirmNewPassword: '',
    },
    validationSchema: ChangePasswordSchema,
    onSubmit: (values) => {
      dispatch(
        changePassword({
          oldPassword: values.currentPassword,
          newPassword: values.newPassword,
        }),
      );
    },
  });

  const [dialogOpen, setDialogOpen] = React.useState(false);

  React.useEffect(() => {
    if (changePasswordStatus === 'success') {
      setDialogOpen(true);
    }
  }, [changePasswordStatus]);

  const [showNewPassword, setShowNewPassword] = React.useState(false);
  const [showPassword, setShowPassword] = React.useState(false);
  const [showConfirmNewPassword, setShowConfirmNewPassword] =
    React.useState(false);

  return (
    <Container component='main' maxWidth='sm'>
      <CssBaseline />
      <Box
        sx={{
          mt: 12,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Typography
          component='h1'
          variant='h5'
          color='secondary'
          sx={{ fontWeight: 'bold', textAlign: 'left' }}
        >
          Change Password
        </Typography>
        <Box
          component='form'
          onSubmit={formik.handleSubmit}
          noValidate
          sx={{
            mt: 1,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <TextField
            variant='outlined'
            margin='normal'
            required
            fullWidth
            id='currentPassword'
            label='Current Password'
            name='currentPassword'
            type={showPassword ? 'text' : 'password'}
            autoFocus
            value={formik.values.currentPassword}
            onChange={formik.handleChange}
            data-testid='currentPassword'
            InputProps={{
              endAdornment: (
                <InputAdornment position='end'>
                  <Tooltip title='Toggle Password Visibility'>
                    <IconButton
                      color='primary'
                      aria-label='Toggle Password Visibility'
                      onClick={() => {
                        setShowPassword(!showPassword);
                      }}
                    >
                      {showPassword ? (
                        <VisibilityOutlined fontSize='small' />
                      ) : (
                        <VisibilityOffOutlined fontSize='small' />
                      )}
                    </IconButton>
                  </Tooltip>
                </InputAdornment>
              ),
            }}
          />
          {formik.errors.currentPassword != null ? (
            <Alert severity='error'>{passwordValidationError}</Alert>
          ) : null}
          <TextField
            variant='outlined'
            margin='normal'
            required
            fullWidth
            id='newPassword'
            label='New Password'
            name='newPassword'
            type={showNewPassword ? 'text' : 'password'}
            value={formik.values.newPassword}
            onChange={formik.handleChange}
            InputProps={{
              endAdornment: (
                <InputAdornment position='end'>
                  <Tooltip title='Toggle Password Visibility'>
                    <IconButton
                      color='primary'
                      aria-label='toggle password visibility'
                      onClick={() => {
                        setShowNewPassword(!showNewPassword);
                      }}
                    >
                      {showNewPassword ? (
                        <VisibilityOutlined fontSize='small' />
                      ) : (
                        <VisibilityOffOutlined fontSize='small' />
                      )}
                    </IconButton>
                  </Tooltip>
                </InputAdornment>
              ),
            }}
          />
          {formik.errors.newPassword != null ? (
            <Alert severity='error'>{passwordValidationError}</Alert>
          ) : null}
          <TextField
            variant='outlined'
            margin='normal'
            required
            fullWidth
            id='confirmNewPassword'
            label='Confirm New Password'
            name='confirmNewPassword'
            type={showConfirmNewPassword ? 'text' : 'password'}
            value={formik.values.confirmNewPassword}
            onChange={formik.handleChange}
            InputProps={{
              endAdornment: (
                <InputAdornment position='end'>
                  <Tooltip title='Toggle Password Visibility'>
                    <IconButton
                      color='primary'
                      aria-label='Toggle Password Visibility'
                      onClick={() => {
                        setShowConfirmNewPassword(!showConfirmNewPassword);
                      }}
                    >
                      {showConfirmNewPassword ? (
                        <VisibilityOutlined fontSize='small' />
                      ) : (
                        <VisibilityOffOutlined fontSize='small' />
                      )}
                    </IconButton>
                  </Tooltip>
                </InputAdornment>
              ),
            }}
          />
          {formik.errors.confirmNewPassword != null ? (
            <Alert severity='error'>{passwordValidationError}</Alert>
          ) : null}
          <Button
            type='submit'
            variant='contained'
            color='primary'
            sx={{
              mt: 3,
              mb: 2,
              width: '30%',
              display: 'block',
              marginLeft: 'auto',
              marginRight: 'auto',
            }}
            onClick={() => formik.handleChange}
          >
            Save Changes
          </Button>
          {changePasswordError != null ? (
            <Alert severity='error' data-testid='firebaseError'>
              {changePasswordError.message}
            </Alert>
          ) : null}
        </Box>
      </Box>
      <Dialog
        open={dialogOpen}
        onClick={() => {
          setDialogOpen(false);
        }}
        aria-labelledby='Change Password Alert'
        aria-describedby='alert-dialog-description'
        maxWidth='sm'
      >
        <DialogTitle id='alert-dialog-title'>
          {'Change Password Succeeded'}
        </DialogTitle>
        <DialogContent>
          <DialogContentText id='alert-dialog-description'>
            Password change succeeded. Do you want to go to the account page?
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setDialogOpen(false);
            }}
            color='primary'
          >
            No
          </Button>
          <Button
            onClick={() => {
              setDialogOpen(false);
              dispatch(changePasswordInit());
              navigateTo('/account');
            }}
            color='primary'
            autoFocus
            cy-data='goToAccount'
          >
            Yes
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
