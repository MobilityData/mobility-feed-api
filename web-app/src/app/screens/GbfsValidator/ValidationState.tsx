import { CheckCircle, ReportOutlined } from '@mui/icons-material';
import {
  Box,
  Container,
  Typography,
  Chip,
  Tooltip,
  useTheme,
  Skeleton,
} from '@mui/material';
import { type ReactElement, useEffect, useMemo } from 'react';
import GbfsFeedSearchInput from './GbfsFeedSearchInput';
import { gbfsValidatorHeroBg } from './ValidationReport.styles';
import ValidationReport from './ValidationReport';
import { useSelector, useDispatch } from 'react-redux';
import { validateStart } from '../../store/gbfs-validator-reducer';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  selectGbfsValidationError,
  selectGbfsValidationLoading,
  selectGbfsValidationResult,
} from '../../store/gbfs-validator-selectors';
import { useGbfsAuth } from '../../context/GbfsAuthProvider';
import { ValidationErrorAlert } from './ValidationErrorAlert';

export default function ValidationState(): ReactElement {
  const theme = useTheme();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { auth } = useGbfsAuth();
  const loadingState = useSelector(selectGbfsValidationLoading);
  const validationResult = useSelector(selectGbfsValidationResult);
  const validationError = useSelector(selectGbfsValidationError);
  const dispatch = useDispatch();
  const feedUrl = searchParams.get('AutoDiscoveryUrl');

  const {
    gbfsVersion,
    numberOfErrors,
    numberOfSystemErrors,
    filesWithErrors,
    isValidFeed,
    validatorVersion,
  } = useMemo(() => {
    const files = validationResult?.summary?.files ?? [];
    const gbfsVersion = files.find((f) => f.version != null)?.version ?? 'N/A';
    const numberOfErrors = files.reduce(
      (acc, f) => acc + (f.errors?.length ?? 0),
      0,
    );
    const numberOfSystemErrors = files.reduce(
      (acc, f) => acc + (f.systemErrors?.length ?? 0),
      0,
    );
    const totalErrors = numberOfErrors + numberOfSystemErrors;
    const filesWithErrors = files.filter(
      (f) => (f.errors?.length ?? 0) > 0,
    ).length;
    const isValidFeed = totalErrors === 0;
    const validatorVersion =
      validationResult?.summary?.validatorVersion ?? 'N/A';
    return {
      gbfsVersion,
      numberOfErrors,
      numberOfSystemErrors,
      filesWithErrors,
      isValidFeed,
      validatorVersion,
    };
  }, [
    validationResult?.summary?.files,
    validationResult?.summary?.validatorVersion,
  ]);

  const triggerDataFetch = (): void => {
    if (feedUrl !== null && feedUrl !== '') {
      dispatch(validateStart({ feedUrl, auth }));
    } else {
      navigate('/gbfs-validator');
    }
  };

  useEffect(() => {
    triggerDataFetch();
  }, [dispatch, feedUrl, auth]);

  return (
    <>
      <Box
        sx={{
          ...gbfsValidatorHeroBg,
          p: 1,
          mt: '-32px',
        }}
      >
        <Container maxWidth='lg' sx={{ my: 2 }}>
          <GbfsFeedSearchInput
            initialFeedUrl={feedUrl ?? ''}
            triggerDataFetch={triggerDataFetch}
          ></GbfsFeedSearchInput>
        </Container>
      </Box>
      <Container maxWidth='lg' sx={{ mb: 4, mt: 2 }}>
        <Box sx={{ mt: 4 }}>
          <Typography variant='h6' sx={{ opacity: 0.8 }}>
            GBFS Feed Validation
          </Typography>
          <Typography
            variant='h4'
            sx={{
              fontWeight: 700,
              mb: 3,
              color: theme.palette.primary.main,
              overflowWrap: 'break-word',
            }}
          >
            {feedUrl}
          </Typography>
        </Box>
        {validationError != null && validationError !== '' && (
          <ValidationErrorAlert
            validationError={validationError}
            triggerDataFetch={triggerDataFetch}
          ></ValidationErrorAlert>
        )}
        {(validationError == null || validationError === '') && (
          <Box
            sx={{
              display: 'flex',
              gap: 1,
              mb: 3,
              flexWrap: 'wrap',
            }}
          >
            {loadingState ? (
              [120, 140, 160, 180].map((w, i) => (
                <Skeleton key={i} variant='rounded' width={w} height={32} />
              ))
            ) : (
              <>
                <Tooltip title='GBFS Version of the feed' placement='top'>
                  <Chip label={`Version ${gbfsVersion}`} color='primary' />
                </Tooltip>
                {isValidFeed && (
                  <Chip
                    icon={<CheckCircle />}
                    label='Valid Feed'
                    color='success'
                  />
                )}
                {!isValidFeed && (
                  <>
                    <Tooltip
                      title='This feed contains errors and does not fully comply with the GBFS specification.'
                      placement='top'
                    >
                      <Chip
                        icon={<ReportOutlined />}
                        label='Invalid Feed'
                        color='error'
                      />
                    </Tooltip>
                    <Chip
                      label={`${numberOfErrors} Total Errors`}
                      color='error'
                      variant='outlined'
                    />

                    <Chip
                      label={`${filesWithErrors} Files Errors`}
                      color='error'
                      variant='outlined'
                    />
                    {numberOfSystemErrors > 0 && (
                      <Chip
                        label={`${numberOfSystemErrors} Total System Errors`}
                        color='warning'
                        variant='outlined'
                      />
                    )}
                  </>
                )}
                <Tooltip
                  title='Version of the GBFS Validator used'
                  placement='top'
                >
                  <Chip
                    label={`Validator v${validatorVersion}`}
                    variant='outlined'
                  />
                </Tooltip>
              </>
            )}
          </Box>
        )}

        {/* TODO: Disabled until map data is implemented
        <Box
          sx={{
            backgroundColor: theme.palette.background.paper,
            borderRadius: '5px',
            mb: 2,
          }}
        >
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              py: 0.5,
              pr: 2,
            }}
          >
            <ContentTitle>Map View</ContentTitle>
            <Button size='small' variant='text'>
              View Full Map Details
            </Button>
          </Box>

          <Box sx={{ px: 2, pb: 2 }}>
            <Map polygon={[{ lat: 37.7749, lng: -122.4194 }]}></Map>
            <Box textAlign={'right'} sx={{ mt: 1 }}></Box>
          </Box>
        </Box> */}

        <ValidationReport
          validationResult={validationResult}
          loading={loadingState}
        ></ValidationReport>
      </Container>
    </>
  );
}
