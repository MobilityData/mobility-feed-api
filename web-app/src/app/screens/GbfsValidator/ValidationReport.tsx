import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Badge,
  Box,
  Button,
  Card,
  CardHeader,
  Chip,
  Collapse,
  Divider,
  Link,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  ListSubheader,
  Typography,
  useTheme,
} from '@mui/material';
import sampleReponse from './sampleResponse.json';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import UnfoldLessIcon from '@mui/icons-material/UnfoldLess';
import UnfoldMoreIcon from '@mui/icons-material/UnfoldMore';
import { type components } from '../../services/feeds/gbfs-validator-types';
import { useRef, useState } from 'react';
import { OpenInNew } from '@mui/icons-material';
import {
  ValidationElementCardStyles,
  ValidationErrorPathStyles,
  ValidationReportTableStyles,
} from './Validator.styles';

export type ValidationResult = components['schemas']['ValidationResult'];
export type GbfsFile = components['schemas']['GbfsFile'];
export type FileError = components['schemas']['FileError'];

export default function ValidationReport(): React.ReactElement {
  const theme = useTheme();
  const validationResult: ValidationResult =
    sampleReponse as unknown as ValidationResult;
  const cardRefs = useRef<Array<HTMLDivElement | null>>([]);

  const [expandedByFile, setExpandedByFile] = useState<
    Record<string, Set<number>>
  >({});
  const [visibleErrorsByFile, setVisibleErrorsByFile] = useState<
    Record<string, boolean>
  >({});

  const toggleExpanded = (
    fileName: string,
    idx: number,
    isExpanded: boolean,
  ): void => {
    setExpandedByFile((prev) => {
      const next = { ...prev };
      const prevSet =
        prev[fileName] != null ? new Set(prev[fileName]) : new Set<number>();
      if (isExpanded) prevSet.add(idx);
      else prevSet.delete(idx);
      next[fileName] = prevSet;
      return next;
    });
  };

  const collapseAllForFile = (fileName: string): void => {
    setExpandedByFile((prev) => ({ ...prev, [fileName]: new Set<number>() }));
  };

  const expandAllForFile = (fileName: string, count: number): void => {
    const set = new Set<number>();
    for (let i = 0; i < count; i++) set.add(i);
    setExpandedByFile((prev) => ({ ...prev, [fileName]: set }));
  };

  const toggleVisibleErrors = (fileName: string): void => {
    setVisibleErrorsByFile((prev) => {
      const nextVisible = !prev[fileName];
      if (!nextVisible) {
        setExpandedByFile((prevExp) => ({
          ...prevExp,
          [fileName]: new Set<number>(),
        }));
      }
      return { ...prev, [fileName]: nextVisible };
    });
  };

  return (
    <>
      {validationResult != null && (
        <Box>
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'nowrap',
              gap: 2,
              maxWidth: 'lg',
              m: 'auto',
            }}
          >
            <Box id='table-content' sx={ValidationReportTableStyles}>
              <List
                aria-labelledby='nested-list-subheader'
                subheader={<ListSubheader>File Summary</ListSubheader>}
              >
                {validationResult?.summary?.files?.map(
                  (file: GbfsFile, index) => {
                    const hasErrors =
                      file.errors != null && file.errors.length > 0;
                    return (
                      <ListItem disablePadding key={file.name}>
                        <ListItemButton
                          onClick={() => cardRefs.current[index]?.focus()}
                        >
                          <ListItemIcon>
                            {hasErrors ? (
                              <Badge
                                badgeContent={file?.errors?.length}
                                color='error'
                              >
                                <ErrorOutlineIcon
                                  sx={{
                                    color: theme.palette.error.main,
                                    mr: 1,
                                  }}
                                />
                              </Badge>
                            ) : (
                              <CheckCircleOutlineIcon
                                sx={{
                                  color: theme.palette.success.main,
                                  mr: 1,
                                }}
                              />
                            )}
                          </ListItemIcon>
                          <ListItemText
                            primary={file.name + '.json'}
                            sx={{
                              color: hasErrors
                                ? theme.palette.error.main
                                : theme.palette.text.primary,
                            }}
                          />
                        </ListItemButton>
                      </ListItem>
                    );
                  },
                )}
              </List>
            </Box>

            <Box
              sx={{
                height: '100%',
                width: '100%',
                borderRadius: '5px',
                backgroundColor: theme.palette.background.paper,
                p: 0,
              }}
            >
              <ListSubheader>Validation Results</ListSubheader>
              {validationResult?.summary?.files?.map(
                (file: GbfsFile, index) => {
                  const hasErrors =
                    file.errors != null && file.errors.length > 0;
                  const errorsCount = file?.errors?.length ?? 0;
                  const fileKey = file.name ?? '';
                  const isAnyExpanded =
                    (expandedByFile[fileKey ?? '']?.size ?? 0) > 0;
                  const isVisible = !!visibleErrorsByFile[fileKey];

                  return (
                    <Card
                      key={file.name}
                      ref={(el) => (cardRefs.current[index] = el)}
                      tabIndex={-1}
                      sx={ValidationElementCardStyles(theme, index)}
                    >
                      <CardHeader
                        sx={{ pb: hasErrors ? 2 : 1 }}
                        title={file.name + '.json'}
                        titleTypographyProps={{
                          variant: 'h6',
                          sx: { fontWeight: 'bold' },
                        }}
                        avatar={
                          hasErrors ? (
                            <ErrorOutlineIcon color='error' />
                          ) : (
                            <CheckCircleOutlineIcon color='success' />
                          )
                        }
                        action={
                          <>
                            <Button
                              size='small'
                              endIcon={<OpenInNew />}
                              color={'inherit'}
                              sx={{ opacity: 0.7 }}
                              component={Link}
                              href={file.url}
                              target='_blank'
                              rel='noopener noreferrer'
                            >
                              View File
                            </Button>
                          </>
                        }
                      />
                      <Box
                        sx={{
                          px: 2,
                          pb: 2,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        {!hasErrors && (
                          <Typography
                            variant='body2'
                            color={theme.palette.success.main}
                          >
                            <b>Valid</b> no errors
                          </Typography>
                        )}
                        {hasErrors && (
                          <Button
                            size='small'
                            color='error'
                            variant='outlined'
                            onClick={() => {
                              toggleVisibleErrors(fileKey);
                            }}
                          >
                            {isVisible ? 'Hide' : 'View'}&#8195;
                            <b>{errorsCount}</b>&#8195;Error Details
                          </Button>
                        )}
                        {hasErrors && isVisible && (
                          <Button
                            size='small'
                            color='inherit'
                            onClick={() => {
                              isAnyExpanded
                                ? collapseAllForFile(fileKey)
                                : expandAllForFile(fileKey, errorsCount);
                            }}
                            startIcon={
                              isAnyExpanded ? (
                                <UnfoldLessIcon />
                              ) : (
                                <UnfoldMoreIcon />
                              )
                            }
                            sx={{ opacity: 0.8, ml: 1 }}
                          >
                            {isAnyExpanded ? 'Collapse all' : 'Expand all'}
                          </Button>
                        )}
                      </Box>

                      {hasErrors && (
                        <Collapse in={isVisible} timeout='auto' unmountOnExit>
                          <Divider />
                          <Box
                            sx={{
                              maxHeight: '400px',
                              overflowY: 'auto',
                              transition: 'height 200ms',
                            }}
                          >
                            {file?.errors?.map((error, idx) => (
                              <Accordion
                                key={idx}
                                slotProps={{
                                  transition: { unmountOnExit: true },
                                }}
                                sx={{
                                  background: theme.palette.background.default,
                                  '&.Mui-expanded': {
                                    m: 0,
                                  },
                                  '.MuiAccordionSummary-content.Mui-expanded': {
                                    my: 1,
                                  },
                                }}
                                expanded={
                                  expandedByFile[fileKey]?.has(idx) ?? false
                                }
                                onChange={(_, isExpanded) => {
                                  toggleExpanded(fileKey, idx, isExpanded);
                                }}
                              >
                                <AccordionSummary
                                  expandIcon={<ExpandMoreIcon />}
                                  aria-controls={`panel-${fileKey}-${idx}-content`}
                                  id={`panel-${fileKey}-${idx}-header`}
                                >
                                  <Chip
                                    size='small'
                                    color='error'
                                    label={`#${idx + 1} - ${error.keyword}`}
                                  />
                                  <Typography sx={{ ml: 2 }}>
                                    {error.message}
                                  </Typography>
                                </AccordionSummary>
                                <AccordionDetails>
                                  <Box>
                                    {error.instancePath != null &&
                                      error.instancePath !== '' && (
                                        <Box
                                          sx={{
                                            display: 'flex',
                                            gap: 2,
                                            alignItems: 'center',
                                          }}
                                        >
                                          <Typography
                                            variant='body2'
                                            sx={{ width: '120px' }}
                                          >
                                            Instance Path:
                                          </Typography>
                                          <code
                                            style={ValidationErrorPathStyles(
                                              theme,
                                            )}
                                          >
                                            {error.instancePath}
                                          </code>
                                        </Box>
                                      )}
                                    {error.schemaPath != null &&
                                      error.schemaPath !== '' && (
                                        <Box
                                          sx={{
                                            display: 'flex',
                                            gap: 2,
                                            alignItems: 'center',
                                            mt: 1,
                                          }}
                                        >
                                          <Typography
                                            variant='body2'
                                            sx={{ width: '120px' }}
                                          >
                                            Schema Path:
                                          </Typography>
                                          <code
                                            style={ValidationErrorPathStyles(
                                              theme,
                                            )}
                                          >
                                            {error.schemaPath}
                                          </code>
                                        </Box>
                                      )}
                                  </Box>
                                </AccordionDetails>
                              </Accordion>
                            ))}
                          </Box>
                        </Collapse>
                      )}
                    </Card>
                  );
                },
              )}
            </Box>
          </Box>
        </Box>
      )}
    </>
  );
}
