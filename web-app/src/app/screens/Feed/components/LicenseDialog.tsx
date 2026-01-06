import React, { useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Typography,
  Box,
  CircularProgress,
  Link,
  Alert,
  Grid,
  Chip,
  Tooltip,
  useTheme,
  useMediaQuery,
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
  const { t } = useTranslation('feeds');
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'));
  const dispatch = useDispatch();
  const status = useSelector(selectLicenseStatus);
  const license = useSelector(selectActiveLicense);
  const errors = useSelector(selectLicenseErrors);

  useEffect(() => {
    if (open && licenseId != undefined) {
      dispatch(loadingLicense({ licenseId }));
    }
  }, [open, licenseId, dispatch]);

  const rulesData = [
    {
      title: t('license.permission'),
      subtitle: t('license.permissionSubtitle'),
      rules: license?.license_rules?.filter(
        (rule) => rule.type === 'permission',
      ),
      color: 'success',
      emptyMessage: t('license.noPermission'),
    },
    {
      title: t('license.condition'),
      subtitle: t('license.conditionSubtitle'),
      rules: license?.license_rules?.filter(
        (rule) => rule.type === 'condition',
      ),
      color: 'warning',
      emptyMessage: t('license.noCondition'),
    },
    {
      title: t('license.limitation'),
      subtitle: t('license.limitationSubtitle'),
      rules: license?.license_rules?.filter(
        (rule) => rule.type === 'limitation',
      ),
      color: 'error',
      emptyMessage: t('license.noLimitation'),
    },
  ];

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth='md'
      fullScreen={fullScreen}
      sx={{ minWidth: 'sm' }}
    >
      <DialogTitle>
        {t('license.dialogTitle')}
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
            {errors.DatabaseAPI?.message ?? t('license.loadingError')}
          </Alert>
        )}

        {status === 'loaded' && license != null && (
          <Box>
            <Box
              sx={{ borderBottom: '1px solid', borderColor: 'divider', py: 1 }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Typography variant='h6'>
                  {license.name ?? license.id}
                </Typography>
                {license?.is_spdx != undefined && license.is_spdx && (
                  <Tooltip title={t('license.spdxTooltip')} placement='top'>
                    <Chip
                      label='SPDX'
                      size='small'
                      color='info'
                      variant='outlined'
                      sx={{ ml: 1, verticalAlign: 'middle' }}
                    />
                  </Tooltip>
                )}
              </Box>
              {license.url != undefined && license.url != '' && (
                <Box mb={2}>
                  <Link
                    href={license.url}
                    target='_blank'
                    rel='noopener noreferrer'
                    sx={{ wordBreak: 'break-word' }}
                  >
                    {license.url}
                  </Link>
                </Box>
              )}
              {license.description != undefined &&
                license.description != '' && (
                  <Typography variant='body1' paragraph>
                    {license.description}
                  </Typography>
                )}
            </Box>
            <Box my={2}>
              {license.license_rules != undefined &&
              license.license_rules.length > 0 ? (
                <>
                  <Grid container spacing={4}>
                    {rulesData.map((ruleData) => {
                      const hasRules =
                        ruleData.rules != undefined &&
                        ruleData.rules.length > 0;
                      return (
                        <Grid size={12} key={ruleData.title}>
                          <Typography
                            variant='h6'
                            sx={{
                              textTransform: 'capitalize',

                              fontWeight: 'bold',
                              color: `${ruleData.color}.main`,
                            }}
                          >
                            {ruleData.title}
                          </Typography>
                          <Typography
                            variant='body2'
                            color='text.secondary'
                            sx={{ mb: 2 }}
                          >
                            {ruleData.subtitle}
                          </Typography>
                          {hasRules ? (
                            <Grid container spacing={2}>
                              {ruleData.rules?.map((rule, index) => (
                                <Grid  size={{xs: 12, md: 6}} key={index}>
                                  <Box
                                    sx={{
                                      p: 1.5,
                                      border: '1px solid',
                                      borderColor: 'divider',
                                      borderRadius: 1,
                                      height: '100%',
                                      borderLeft: '5px solid',
                                      borderLeftColor: `${ruleData.color}.main`,
                                    }}
                                  >
                                    <Box
                                      sx={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'flex-start',
                                        mb: 0.5,
                                      }}
                                    >
                                      <Typography
                                        variant='subtitle1'
                                        fontWeight='bold'
                                        sx={{ mr: 1 }}
                                      >
                                        {rule.label ?? rule.name}
                                      </Typography>
                                    </Box>
                                    <Typography
                                      variant='body2'
                                      color='text.secondary'
                                    >
                                      {rule.description}
                                    </Typography>
                                  </Box>
                                </Grid>
                              ))}
                            </Grid>
                          ) : (
                            <Typography
                              variant='body2'
                              color='text.secondary'
                              sx={{ fontStyle: 'italic' }}
                            >
                              {ruleData.emptyMessage}
                            </Typography>
                          )}
                        </Grid>
                      );
                    })}
                  </Grid>
                </>
              ) : (
                <>
                  <Typography variant='h6'>{t('license.noRules')}</Typography>
                  <Typography variant='subtitle1' color='text.secondary' mb={2}>
                    {t('license.contributeMessage')}
                  </Typography>
                  <Link
                    href={`https://github.com/MobilityData/licenses-aas/blob/main/data/licenses/${license.id}.json`}
                    target='_blank'
                    rel='noopener noreferrer'
                  >
                    https://github.com/MobilityData/licenses-aas/blob/main/data/licenses/
                    {license.id}.json
                  </Link>
                </>
              )}
            </Box>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
}
