import React, { useState } from 'react';
import {
  Box,
  Button,
  Collapse,
  Typography,
  Stack,
  Card,
  CardContent,
  Alert,
} from '@mui/material';

export interface SentryErrorFallbackProps {
  error: unknown;
  eventId?: string;
  resetError?: () => void;
}

const formatError = (error: unknown): string => {
  if (error instanceof Error) {
    return `${error.message}\n${error.stack}`;
  }
  try {
    return typeof error === 'string' ? error : JSON.stringify(error, null, 2);
  } catch {
    return String(error);
  }
};

export const SentryErrorFallback: React.FC<SentryErrorFallbackProps> = ({
  error,
  eventId,
  resetError,
}) => {
  const [showDetails, setShowDetails] = useState(false);
  const details = formatError(error);
  return (
    <Box sx={{ p: 4, maxWidth: 760, m: '40px auto' }}>
      <Card variant='outlined'>
        <CardContent>
          <Stack spacing={2}>
            <Alert severity='error' variant='outlined'>
              <Typography
                variant='h5'
                component='h2'
                sx={{ mb: 1, fontWeight: 600 }}
              >
                Something went wrong
              </Typography>
              <Typography variant='body2'>
                Our team has been notified. You can try reloading or attempt to
                recover.
              </Typography>
            </Alert>
            {eventId != null && (
              <Typography variant='caption' color='text.secondary'>
                Event ID: {eventId}
              </Typography>
            )}
            <Stack direction='row' spacing={1}>
              <Button
                variant='contained'
                color='error'
                onClick={() => {
                  window.location.reload();
                }}
              >
                Reload Page
              </Button>
              {resetError != null && (
                <Button variant='outlined' color='primary' onClick={resetError}>
                  Try Again
                </Button>
              )}
              <Button
                variant='text'
                color='inherit'
                onClick={() => {
                  setShowDetails((v) => !v);
                }}
              >
                {showDetails ? 'Hide Details' : 'Show Details'}
              </Button>
            </Stack>
            <Collapse in={showDetails} unmountOnExit>
              <Box
                sx={{
                  mt: 1,
                  p: 2,
                  bgcolor: 'background.default',
                  borderRadius: 1,
                  fontFamily: 'monospace',
                  fontSize: 12,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  maxHeight: 300,
                  overflow: 'auto',
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              >
                {details}
              </Box>
            </Collapse>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
};

export default SentryErrorFallback;
