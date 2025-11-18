import { Refresh, ContentCopy } from '@mui/icons-material';
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Snackbar,
  Typography,
  useTheme,
} from '@mui/material';
import React, { useState } from 'react';
import { AlertErrorBoxStyles } from './ValidationReport.styles';

interface ValidationErrorAlertProps {
  validationError: string | null;
  triggerDataFetch: () => void;
}

export function ValidationErrorAlert({
  validationError,
  triggerDataFetch,
}: ValidationErrorAlertProps): React.ReactElement {
  const theme = useTheme();
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const errorText = validationError ?? '';
  return (
    <>
      <Alert
        severity='error'
        sx={{ mb: 2, '.MuiAlert-message ': { width: '100%' } }}
      >
        <AlertTitle
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: 1,
          }}
        >
          <Box component='span'>GBFS validation failed</Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              size='small'
              variant='text'
              startIcon={<Refresh />}
              onClick={triggerDataFetch}
              color='secondary'
            >
              Retry
            </Button>
            <Button
              size='small'
              variant='text'
              startIcon={<ContentCopy />}
              color='secondary'
              onClick={() => {
                setSnackbarOpen(true);
                void navigator.clipboard.writeText(errorText);
              }}
            >
              Copy details
            </Button>
          </Box>
        </AlertTitle>
        <Typography variant='body2' sx={{ mb: 1 }}>
          We couldn&apos;t validate the feed at the URL above. Details:
        </Typography>
        <Box component='pre' sx={AlertErrorBoxStyles(theme, showDetails)}>
          {errorText}
        </Box>
        {errorText.length > 300 && (
          <Button
            size='small'
            sx={{ mt: 1 }}
            onClick={() => {
              setShowDetails(!showDetails);
            }}
          >
            {showDetails ? 'Show less' : 'Show more'}
          </Button>
        )}
      </Alert>
      <Snackbar
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        open={snackbarOpen}
        autoHideDuration={5000}
        onClose={() => {
          setSnackbarOpen(false);
        }}
        message={'Error text copied to clipboard'}
        action={
          <Button
            color='inherit'
            size='small'
            onClick={() => setSnackbarOpen(false)}
            aria-label='Close'
          >
            Close
          </Button>
        }
      />
    </>
  );
}
