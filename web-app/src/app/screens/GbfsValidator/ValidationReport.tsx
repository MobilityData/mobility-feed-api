import {
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
import UnfoldLessIcon from '@mui/icons-material/UnfoldLess';
import LanguageIcon from '@mui/icons-material/Language';
import UnfoldMoreIcon from '@mui/icons-material/UnfoldMore';
import { type components } from '../../services/feeds/gbfs-validator-types';
import { useEffect, useMemo, useRef, useState } from 'react';
import { OpenInNew } from '@mui/icons-material';
import {
  ValidationReportTableStyles,
  ContentTitle,
  ValidationElementCardStyles,
  ValidationErrorPathStyles,
  rowButtonOutlineErrorSx,
} from './ValidationReport.styles';
import { langCodeToName } from '../../services/feeds/utils';
import { groupErrorsByFile } from './errorGrouping';
import { ValidationReportSkeletonLoading } from './ValidationReportSkeletonLoading';
import ErrorDetailsDialog from './components/ErrorDetailsDialog';

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
  const [visibleSystemErrorsByFile, setVisibleSystemErrorsByFile] = useState<
    Record<string, boolean>
  >({});
  const [groupedExpanded, setGroupedExpanded] = useState<
    Record<string, boolean>
  >({});
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
  // Group errors by fileName, normalized instancePath and message. Shared util ensures consistency.
  const groupedByFile = useMemo(
    () => groupErrorsByFile(filesForLanguage),
    [filesForLanguage],
  );
  const fileGroupRefs = useRef<Array<HTMLDivElement | null>>([]);

  // Error details dialog selection state
  const [detailsOpen, setDetailsOpen] = useState<boolean>(false);
  const [detailsFileName, setDetailsFileName] = useState<string>('');
  const [detailsFileUrl, setDetailsFileUrl] = useState<string | undefined>(
    undefined,
  );
  const [detailsError, setDetailsError] = useState<FileError | null>(null);

  const openDetails = (
    fileName: string,
    fileUrl: string | undefined,
    err: FileError,
  ): void => {
    setDetailsFileName(fileName);
    setDetailsFileUrl(fileUrl);
    setDetailsError(err);
    setDetailsOpen(true);
  };

  const closeDetails = (): void => {
    setDetailsOpen(false);
  };

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
                  const fg = groupedByFile[index];
                  const numberOfErrors = file.errors?.length ?? 0;
                  const uniqueCount = fg?.groups.length ?? 0;
                  const sysCount = fg?.systemErrors?.length ?? 0;
                  const hasErrors = uniqueCount > 0;
                  const hasSystemErrors = sysCount > 0;
                  const totalCount = numberOfErrors + sysCount;
                  const secondary =
                    hasErrors || hasSystemErrors
                      ? [
                          hasErrors ? `${uniqueCount} unique errors` : null,
                          hasSystemErrors ? `${sysCount} system errors` : null,
                        ]
                          .filter(Boolean)
                          .join(' • ')
                      : '';
                  return (
                    <ListItem disablePadding key={file.name}>
                      <ListItemButton
                        onClick={() => fileGroupRefs.current[index]?.focus()}
                      >
                        <ListItemIcon>
                          {totalCount > 0 ? (
                            <Badge
                              badgeContent={totalCount}
                              color={hasErrors ? 'error' : 'warning'}
                            >
                              {hasErrors ? (
                                <ErrorOutlineIcon
                                  sx={{
                                    color: theme.palette.error.main,
                                    mr: 1,
                                  }}
                                />
                              ) : (
                                <WarningAmberOutlinedIcon
                                  sx={{
                                    color: theme.palette.warning.main,
                                    mr: 1,
                                  }}
                                />
                              )}
                            </Badge>
                          ) : (
                            <CheckCircleOutlineIcon
                              sx={{ color: theme.palette.success.main, mr: 1 }}
                            />
                          )}
                        </ListItemIcon>
                        <ListItemText
                          primary={`${file.name}.json`}
                          secondary={secondary}
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
              {groupedByFile.map((fg, index) => (
                <Card
                  key={fg.fileName}
                  ref={(el) => (fileGroupRefs.current[index] = el)}
                  tabIndex={-1}
                  sx={ValidationElementCardStyles(theme, index)}
                >
                  <CardHeader
                    sx={{
                      pb:
                        fg.total > 0 || (fg.systemErrors?.length ?? 0) > 0
                          ? 2
                          : 1,
                      flexWrap: { xs: 'wrap', sm: 'nowrap' },
                      gap: { xs: 1, sm: 0 },
                    }}
                    title={`${fg.fileName}.json`}
                    titleTypographyProps={{
                      variant: 'h6',
                      sx: { fontWeight: 'bold' },
                    }}
                    avatar={
                      fg.total > 0 ? (
                        <ErrorOutlineIcon color='error' />
                      ) : (fg.systemErrors?.length ?? 0) > 0 ? (
                        <WarningAmberOutlinedIcon color='warning' />
                      ) : (
                        <CheckCircleOutlineIcon color='success' />
                      )
                    }
                    action={
                      <Box
                        sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                      >
                        {fg.total > 0 && (
                          <Chip
                            size='small'
                            color='error'
                            variant='outlined'
                            label={`${fg.total} errors`}
                          />
                        )}
                        {fg.fileUrl != null && fg.fileUrl !== '' && (
                          <Button
                            size='small'
                            endIcon={<OpenInNew />}
                            color={'inherit'}
                            sx={{ opacity: 0.7 }}
                            component={Link}
                            href={fg.fileUrl}
                            target='_blank'
                            rel='noopener noreferrer'
                          >
                            View File
                          </Button>
                        )}
                      </Box>
                    }
                  />
                  {((fg.total === 0 && (fg.systemErrors?.length ?? 0) === 0) ||
                    (fg.systemErrors?.length ?? 0) > 0) && (
                    <Box
                      sx={{
                        px: 2,
                        pb: 2,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      {fg.total === 0 &&
                        (fg.systemErrors?.length ?? 0) === 0 && (
                          <Typography
                            variant='body2'
                            color={theme.palette.success.main}
                          >
                            <b>Valid</b> no errors
                          </Typography>
                        )}
                      {(fg.systemErrors?.length ?? 0) > 0 && (
                        <Button
                          size='small'
                          color='warning'
                          variant='outlined'
                          onClick={() => {
                            setVisibleSystemErrorsByFile((prev) => ({
                              ...prev,
                              [fg.fileName]: !prev[fg.fileName],
                            }));
                          }}
                        >
                          {visibleSystemErrorsByFile[fg.fileName]
                            ? 'Hide'
                            : 'View'}
                          &#8195;
                          <b>{fg.systemErrors?.length ?? 0}</b>&#8195;System
                          Error Details
                        </Button>
                      )}
                    </Box>
                  )}

                  {(fg.groups.length > 0 || fg.systemErrors?.length > 0) && (
                    <Box sx={{ px: 2, pb: 2 }}>
                      {fg.groups.map((group, i) => (
                        <Box
                          key={group.key}
                          sx={{
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 0.25,
                            py: 0.75,
                            borderBottom:
                              i < fg.groups.length - 1 ? '1px solid' : 'none',
                            borderColor: 'divider',
                          }}
                        >
                          {(() => {
                            const groupId = `${fg.fileName}::${group.key}`;
                            const expanded = !!groupedExpanded[groupId];
                            return (
                              <>
                                <Box
                                  sx={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 1.5,
                                    flexWrap: { xs: 'wrap', sm: 'nowrap' },
                                  }}
                                >
                                  <Chip
                                    size='small'
                                    color='error'
                                    label={`${group.occurrences[0].error.keyword}`}
                                  />
                                  <Typography sx={{ fontWeight: 600 }}>
                                    {group.message.replace(':', '')}
                                  </Typography>
                                  <Box sx={{ flexGrow: 1 }} />
                                  <Button
                                    size='small'
                                    color='inherit'
                                    onClick={() => {
                                      setGroupedExpanded((prev) => ({
                                        ...prev,
                                        [groupId]: !expanded,
                                      }));
                                    }}
                                    startIcon={
                                      expanded ? (
                                        <UnfoldLessIcon />
                                      ) : (
                                        <UnfoldMoreIcon />
                                      )
                                    }
                                    sx={{
                                      opacity: 0.8,
                                      minWidth: {
                                        xs: 'auto',
                                        sm: '125px',
                                        md: '225px',
                                      },
                                    }}
                                  >
                                    {/* Responsive label: hide the word 'occurrences' on md down */}
                                    <Box
                                      component='span'
                                      sx={{
                                        display: { xs: 'inline', md: 'none' },
                                      }}
                                    >
                                      {expanded ? 'Hide' : 'Show'} (
                                      {group.occurrences.length})
                                    </Box>
                                    <Box
                                      component='span'
                                      sx={{
                                        display: { xs: 'none', md: 'inline' },
                                      }}
                                    >
                                      {expanded ? 'Hide' : 'Show'} occurrences (
                                      {group.occurrences.length})
                                    </Box>
                                  </Button>
                                </Box>
                                {group.message !== '' && (
                                  <Typography
                                    variant='body2'
                                    color='text.secondary'
                                    sx={{
                                      ml: { xs: 0, sm: 2.5 },
                                      overflowX: 'auto',
                                    }}
                                  >
                                    {group.normalizedPath}
                                  </Typography>
                                )}
                                <Collapse
                                  in={expanded}
                                  timeout='auto'
                                  unmountOnExit
                                >
                                  {group.occurrences.length > 0 && (
                                    <Box
                                      sx={{
                                        display: 'flex',
                                        flexWrap: 'wrap',
                                        gap: 1,
                                        ml: { xs: 0, sm: 2 },
                                        mt: 0.5,
                                        maxHeight: '500px',
                                        overflowY: 'auto',
                                        p: 0.5,
                                      }}
                                    >
                                      {group.occurrences.map((occ, j) => (
                                        <Box
                                          key={j}
                                          role='button'
                                          tabIndex={0}
                                          aria-label={`View details for path ${
                                            occ.error.instancePath ?? '#'
                                          }`}
                                          onClick={() => {
                                            openDetails(
                                              fg.fileName,
                                              fg.fileUrl,
                                              occ.error,
                                            );
                                          }}
                                          onKeyDown={(e) => {
                                            if (
                                              e.key === 'Enter' ||
                                              e.key === ' '
                                            ) {
                                              e.preventDefault();
                                              openDetails(
                                                fg.fileName,
                                                fg.fileUrl,
                                                occ.error,
                                              );
                                            }
                                          }}
                                          sx={{
                                            ...ValidationErrorPathStyles(theme),
                                            position: 'relative',
                                            transition:
                                              'background-color 120ms, box-shadow 120ms',
                                            cursor: 'pointer',
                                            '&:hover': {
                                              boxShadow: `0 0 0 2px ${theme.palette.error.light}`,
                                            },
                                            '&:focus-visible': {
                                              outline: 'none',
                                              boxShadow: `0 0 0 3px ${theme.palette.error.main}`,
                                            },
                                            '&:hover .hover-details-btn, &:focus-visible .hover-details-btn':
                                              {
                                                opacity: 0.7,

                                                pointerEvents: 'auto',
                                              },
                                          }}
                                        >
                                          <Typography
                                            component='span'
                                            variant='caption'
                                            sx={{
                                              fontFamily: 'monospace',
                                              pr: 3,
                                            }}
                                          >
                                            {occ.error.instancePath ?? '#'}
                                          </Typography>
                                          {/* This box is used as an indicator to show users to click the row
                                          It cannot be a button alone because of accessibility issues with nested buttons */}
                                          <Box
                                            component='span'
                                            className='hover-details-btn'
                                            sx={rowButtonOutlineErrorSx}
                                          >
                                            Click for details
                                          </Box>
                                        </Box>
                                      ))}
                                    </Box>
                                  )}
                                </Collapse>
                              </>
                            );
                          })()}
                        </Box>
                      ))}
                      {(fg.systemErrors?.length ?? 0) > 0 && (
                        <Collapse
                          in={!!visibleSystemErrorsByFile[fg.fileName]}
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
                            {fg.systemErrors?.map(
                              (
                                error: components['schemas']['SystemError'],
                                idx: number,
                              ) => (
                                <Box
                                  key={`sys-${idx}`}
                                  sx={{
                                    p: 1.5,
                                    borderBottom:
                                      idx < (fg.systemErrors?.length ?? 0) - 1
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
                              ),
                            )}
                          </Box>
                        </Collapse>
                      )}
                    </Box>
                  )}
                </Card>
              ))}
            </Box>
          </Box>
        </Box>
      )}
      <ErrorDetailsDialog
        open={detailsOpen}
        onClose={closeDetails}
        fileName={detailsFileName}
        fileUrl={detailsFileUrl}
        error={detailsError}
      />
    </>
  );
}
