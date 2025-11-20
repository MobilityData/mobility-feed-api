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
  Tabs,
  Tab,
  Typography,
  useTheme,
  Tooltip,
} from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import UnfoldLessIcon from '@mui/icons-material/UnfoldLess';
import LanguageIcon from '@mui/icons-material/Language';
import UnfoldMoreIcon from '@mui/icons-material/UnfoldMore';
import { type components } from '../../services/feeds/gbfs-validator-types';
import { useEffect, useRef, useState } from 'react';
import { OpenInNew } from '@mui/icons-material';
import {
  ValidationReportTableStyles,
  ContentTitle,
  ValidationElementCardStyles,
  ValidationErrorPathStyles,
} from './ValidationReport.styles';
import { langCodeToName } from '../../services/feeds/utils';
import { ValidationReportSkeletonLoading } from './ValidationReportSkeletonLoading';

export type ValidationResult = components['schemas']['ValidationResult'];
export type GbfsFile = components['schemas']['GbfsFile'];
export type FileError = components['schemas']['FileError'];

interface ValidationResultProps {
  validationResult: ValidationResult | undefined;
  loading: boolean;
}

export default function ValidationReport({
  validationResult,
  loading,
}: ValidationResultProps): React.ReactElement {
  const theme = useTheme();
  const cardRefs = useRef<Array<HTMLDivElement | null>>([]);

  const [expandedByFile, setExpandedByFile] = useState<
    Record<string, Set<number>>
  >({});
  const [visibleErrorsByFile, setVisibleErrorsByFile] = useState<
    Record<string, boolean>
  >({});
  const [visibleSystemErrorsByFile, setVisibleSystemErrorsByFile] = useState<
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

  const toggleVisibleSystemErrors = (fileName: string): void => {
    setVisibleSystemErrorsByFile((prev) => {
      const nextVisible = !prev[fileName];
      return { ...prev, [fileName]: nextVisible };
    });
  };

  const allFiles: GbfsFile[] = validationResult?.summary?.files ?? [];
  const baseFiles: GbfsFile[] = allFiles.filter((f) => f.language == null);
  const languageSpecificFiles: GbfsFile[] = allFiles.filter(
    (f) => f.language != null,
  );
  const languages = Array.from(
    new Set(languageSpecificFiles.map((f) => f.language ?? '')),
  ).sort();
  const [selectedLanguage, setSelectedLanguage] = useState<string>(
    languages[0] ?? '',
  );

  // Adjust selectedLanguage if languages set changes (e.g., after loading finishes)
  useEffect(() => {
    if (languages.length > 0 && !languages.includes(selectedLanguage)) {
      setSelectedLanguage(languages[0]);
    }
  }, [languages, selectedLanguage]);

  const filesForLanguage: GbfsFile[] =
    selectedLanguage !== ''
      ? [
          ...baseFiles,
          ...languageSpecificFiles.filter(
            (f) => f.language === selectedLanguage,
          ),
        ]
      : [...baseFiles];

  if (loading) {
    return <ValidationReportSkeletonLoading></ValidationReportSkeletonLoading>;
  }

  return (
    <>
      {validationResult != null && (
        <Box>
          {languages.length > 1 && (
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <Tooltip title='Language of the feed' placement='top'>
                <LanguageIcon aria-label='Language of the feed' />
              </Tooltip>

              <Tabs
                value={selectedLanguage}
                onChange={(_, v) => {
                  setSelectedLanguage(v);
                }}
                variant='scrollable'
              >
                {languages.map((lng) => (
                  <Tab key={lng} value={lng} label={langCodeToName(lng)} />
                ))}
              </Tabs>
            </Box>
          )}
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
                sx={{ maxHeight: '90vh', overflowY: 'auto' }}
                subheader={
                  <ListSubheader sx={{ zIndex: 200 }}>
                    File Summary{' '}
                    {languages.length > 1
                      ? `(${langCodeToName(selectedLanguage)})`
                      : ''}
                  </ListSubheader>
                }
              >
                {filesForLanguage.map((file: GbfsFile, index) => {
                  const hasErrors =
                    file.errors != null && file.errors.length > 0;
                  const hasSystemErrors =
                    file.systemErrors != null && file.systemErrors.length > 0;
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
                          ) : hasSystemErrors ? (
                            <Badge
                              badgeContent={file?.systemErrors?.length}
                              color='warning'
                            >
                              <WarningAmberOutlinedIcon
                                sx={{
                                  color: theme.palette.warning.main,
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
                              : hasSystemErrors
                                ? theme.palette.warning.main
                                : theme.palette.text.primary,
                          }}
                        />
                      </ListItemButton>
                    </ListItem>
                  );
                })}
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
              <ContentTitle>
                Validation Results{' '}
                {languages.length > 1
                  ? `(${langCodeToName(selectedLanguage)})`
                  : ''}
              </ContentTitle>
              {filesForLanguage.map((file: GbfsFile, index) => {
                const hasErrors = file.errors != null && file.errors.length > 0;
                const hasSystemErrors =
                  file.systemErrors != null && file.systemErrors.length > 0;
                const errorsCount = file?.errors?.length ?? 0;
                const systemErrorsCount = file?.systemErrors?.length ?? 0;
                const fileKey = file.name ?? '';
                const isAnyExpanded =
                  (expandedByFile[fileKey ?? '']?.size ?? 0) > 0;
                const isVisible = !!visibleErrorsByFile[fileKey];
                const isSystemVisible = !!visibleSystemErrorsByFile[fileKey];

                return (
                  <Card
                    key={file.name}
                    ref={(el) => (cardRefs.current[index] = el)}
                    tabIndex={-1}
                    sx={ValidationElementCardStyles(theme, index)}
                  >
                    <CardHeader
                      sx={{ pb: hasErrors || hasSystemErrors ? 2 : 1 }}
                      title={file.name + '.json'}
                      titleTypographyProps={{
                        variant: 'h6',
                        sx: { fontWeight: 'bold' },
                      }}
                      avatar={
                        hasErrors ? (
                          <ErrorOutlineIcon color='error' />
                        ) : hasSystemErrors ? (
                          <WarningAmberOutlinedIcon color='warning' />
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
                      {!hasErrors && !hasSystemErrors && (
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
                      {hasSystemErrors && (
                        <Button
                          size='small'
                          color='warning'
                          variant='outlined'
                          onClick={() => {
                            toggleVisibleSystemErrors(fileKey);
                          }}
                          sx={{ ml: hasErrors ? 1 : 0 }}
                        >
                          {isSystemVisible ? 'Hide' : 'View'}&#8195;
                          <b>{systemErrorsCount}</b>&#8195;System Error Details
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
                    {hasSystemErrors && (
                      <Collapse
                        in={isSystemVisible}
                        timeout='auto'
                        unmountOnExit
                      >
                        <Divider />
                        <Box
                          sx={{
                            maxHeight: '400px',
                            overflowY: 'auto',
                            transition: 'height 200ms',
                          }}
                        >
                          {file?.systemErrors?.map((error, idx: number) => (
                            <Box
                              key={`sys-${idx}`}
                              sx={{
                                p: 1.5,
                                borderBottom:
                                  idx < systemErrorsCount - 1
                                    ? '1px solid'
                                    : 'none',
                                borderColor: 'divider',
                                display: 'flex',
                                alignItems: 'center',
                              }}
                            >
                              <Chip
                                size='small'
                                color='warning'
                                label={`#${idx + 1} - ${error.error}`}
                              />
                              <Typography sx={{ ml: 2 }}>
                                {error.message}
                              </Typography>
                            </Box>
                          ))}
                        </Box>
                      </Collapse>
                    )}
                  </Card>
                );
              })}
            </Box>
          </Box>
        </Box>
      )}
    </>
  );
}
