import { Box, Typography, useTheme } from '@mui/material';
import sampleReponse from './sampleResponse.json';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';

export interface ValidationResult {
  summary: {
    validatorVersion: string;
    files: GbfsFile[];
  };
}

export interface GbfsFile {
  name: string;
  url: string;
  version: string;
  language?: string | null;
  errors: FileError[];
  schema: object;
}

export interface FileError {
  keyword: string;
  instancePath: string;
  schemaPath: string;
  message: string;
  params: {
    [key: string]: any;
  };
}

export default function ValidationReport(): React.ReactElement {
  const theme = useTheme();
  const validationResult: ValidationResult = sampleReponse as ValidationResult;
  return (
    <Box sx={{ mt: 5 }}>
      <Box
        sx={{
          textAlign: 'center',
          justifyContent: 'center',
          alignItems: 'center',
          mb: 2,
        }}
      >
        <Typography variant='h4' sx={{ fontWeight: 700, mb: 2 }}>
          Validation Report
        </Typography>
        <Typography variant='body1' sx={{ fontWeight: 700, mb: 2, ml: 2 }}>
          https://tor.publicbikesystem.net/customer/gbfs/v2/gbfs.json
        </Typography>
        <Typography variant='body1' sx={{ fontWeight: 700, mb: 2, ml: 2 }}>
          Validator Version: {validationResult.summary.validatorVersion}
        </Typography>
        <Typography variant='body1' sx={{ fontWeight: 700, mb: 2, ml: 2 }}>
          Invalid GBFS Feed
        </Typography>
      </Box>

      <Box
        sx={{
          display: 'flex',
          flexWrap: 'nowrap',
          height: '700px',
          gap: 2,
          maxWidth: 'lg',
          m: 'auto',
        }}
      >
        <Box
          id='table-content'
          sx={{
            backgroundColor: theme.palette.background.paper,
            height: '100%',
            position: 'relative',
            width: '300px',
          }}
        >
          <Typography variant='h5' sx={{ fontWeight: 700, mb: 2, ml: 2 }}>
            Validation Summary
          </Typography>
          <Typography variant='body1' sx={{ fontWeight: 700, mb: 2, ml: 2 }}>
            Total Errors: 3
          </Typography>

          {validationResult.summary.files.map((file: GbfsFile) => {
            const hasErrors = file.errors.length > 0;
            return (
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography>{file.name}</Typography>
                    {hasErrors ? (
                    <ErrorOutlineIcon
                      fontSize='small'
                      sx={{ color: theme.palette.error.main, mr: 1 }}
                    />
                  ) : (
                    <CheckCircleOutlineIcon
                      fontSize='small'
                      sx={{ color: theme.palette.success.main, mr: 1 }}
                    />
                  )}
                </Box>
            )
          })}

        </Box>



        <Box
          sx={{
            height: '100%',
            width: '100%',
            overflowY: 'scroll',
            backgroundColor: theme.palette.background.paper,
          }}
        >
          {validationResult.summary.files.map((file: GbfsFile) => {
            const hasErrors = file.errors.length > 0;
            return (
              <Box
                key={file.name}
                sx={{
                  backgroundColor: hasErrors
                    ? theme.palette.error.light
                    : theme.palette.success.light,
                  position: 'relative',
                  p: 2,
                }}
              >
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography
                    variant='h5'
                    sx={{ fontWeight: 700, mb: 0, ml: 2 }}
                  >
                    {file.name}.json
                  </Typography>
                  {hasErrors ? (
                    <ErrorOutlineIcon
                      fontSize='large'
                      sx={{ color: theme.palette.error.main, mr: 1 }}
                    />
                  ) : (
                    <CheckCircleOutlineIcon
                      fontSize='large'
                      sx={{ color: theme.palette.success.main, mr: 1 }}
                    />
                  )}
                </Box>

                {hasErrors && (
                  <>
                    <Typography
                      variant='body1'
                      sx={{ fontWeight: 700, mb: 2, ml: 2 }}
                    >
                      Errors:
                    </Typography>
                    {file.errors.map((error) => (
                      <Box key={error.instancePath} sx={{ ml: 4 }}>
                        <Typography
                          variant='body1'
                          sx={{ fontWeight: 700, mb: 2 }}
                        >
                          {error.message}
                        </Typography>
                      </Box>
                    ))}
                  </>
                )}
              </Box>
            );
          })}
        </Box>
      </Box>
    </Box>
  );
}
