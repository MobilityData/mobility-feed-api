import React, { useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Typography,
  Box,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  Link,
  Alert,
  Grid,
  Chip,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { useSelector, useDispatch } from 'react-redux';
import {
  selectActiveLicense,
  selectLicenseStatus,
  selectLicenseErrors,
} from '../../../store/license-selectors';
import { loadingLicense } from '../../../store/license-reducer';
import { useTranslation } from 'react-i18next';

export interface LicenseDialogProps {
  open: boolean;
  onClose: () => void;
  licenseId: string | undefined;
}

export default function LicenseDialog({
  open,
  onClose,
  licenseId,
}: LicenseDialogProps): React.ReactElement {
  const { t } = useTranslation('feeds'); // Adjust namespace if needed
  const dispatch = useDispatch();
  const status = useSelector(selectLicenseStatus);
  const license = useSelector(selectActiveLicense);
  const errors = useSelector(selectLicenseErrors);

  useEffect(() => {
    if (open && licenseId) {
      dispatch(loadingLicense({ licenseId }));
    }
  }, [open, licenseId, dispatch]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth='md' fullWidth>
      <DialogTitle>
        License Details
        <IconButton
          aria-label='close'
          onClick={onClose}
          sx={{
            position: 'absolute',
            right: 8,
            top: 8,
            color: (theme) => theme.palette.grey[500],
          }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {status === 'loading' && (
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              minHeight: '200px',
            }}
          >
            <CircularProgress />
          </Box>
        )}

        {status === 'error' && (
          <Alert severity='error'>
            {errors.DatabaseAPI?.message || 'Error loading license details'}
          </Alert>
        )}

        {status === 'loaded' && license != null && (
          <Box>
            <Typography variant='h6' gutterBottom>
              {license.name || license.id}
            </Typography>
            {license.url && (
              <Box mb={2}>
                <Link
                  href={license.url}
                  target='_blank'
                  rel='noopener noreferrer'
                >
                  {license.url}
                </Link>
              </Box>
            )}
            {license.description && (
              <Typography variant='body1' paragraph>
                {license.description}
              </Typography>
            )}

            {license.license_rules && license.license_rules.length > 0 && (
              <Box mt={2}>
                <Typography variant='h6' gutterBottom>
                  Rules
                </Typography>
                <Grid container spacing={2}>
                  {license.license_rules.map((rule, index) => (
                    <Grid item xs={12} md={6} key={index}>
                      <Box
                        sx={{
                          p: 1.5,
                          border: '1px solid',
                          borderColor: 'divider',
                          borderRadius: 1,
                          height: '100%',
                        }}
                      >
                        <Box
                          sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'flex-start',
                            mb: 1,
                          }}
                        >
                          <Typography
                            variant='subtitle1'
                            fontWeight='bold'
                            sx={{ mr: 1 }}
                          >
                            {rule.label || rule.name}
                          </Typography>
                          {rule.type && (
                            <Chip
                              label={rule.type}
                              size='small'
                              color={
                                rule.type === 'permission'
                                  ? 'success'
                                  : rule.type === 'condition'
                                  ? 'warning'
                                  : 'error'
                              }
                              variant='outlined'
                            />
                          )}
                        </Box>
                        <Typography variant='body2' color='text.secondary'>
                          {rule.description}
                        </Typography>
                      </Box>
                    </Grid>
                  ))}
                </Grid>
              </Box>
            )}
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
}
