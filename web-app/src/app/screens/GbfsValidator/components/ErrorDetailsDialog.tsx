import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Link,
  Tooltip,
  Typography,
  useTheme,
  IconButton,
  useMediaQuery,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { OpenInNew } from '@mui/icons-material';
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { type components } from '../../../services/feeds/gbfs-validator-types';
import {
  resolveJsonPointer,
  getPointerSegments,
  getMissingKeyFromMessage,
  type JSONValue,
} from '../errorDetailsUtils';
import {
  getCachedJson,
  setCachedJson,
  clearExpiredCaches,
} from './gbfsContextCache';
import { useGbfsAuth } from '../../../context/GbfsAuthProvider';
import { removePathFromMessage } from '../errorGrouping';
import {
  dialogTitleSx,
  highlightedPreSx,
  highlightedContainerSx,
  highlightedTitleSx,
  highlightedInnerSx,
  entryRowSx,
  keyTypographySx,
  listItemSx,
  valueTypographySx,
  outlinePreSx,
  ValidationErrorPathStyles,
} from '../ValidationReport.styles';
import DataObjectIcon from '@mui/icons-material/DataObject';

export type FileError = components['schemas']['FileError'];

interface ErrorDetailsDialogProps {
  open: boolean;
  onClose: () => void;
  fileName: string;
  fileUrl?: string;
  error: FileError | null;
}

export function ErrorDetailsDialog({
  open,
  onClose,
  fileName,
  fileUrl,
  error,
}: ErrorDetailsDialogProps): React.ReactElement | null {
  const theme = useTheme();
  const offendingRef = useRef<HTMLDivElement | null>(null);
  const { buildAuthHeaders } = useGbfsAuth();
  const [loadingContext, setLoadingContext] = useState<boolean>(false);
  const [contextData, setContextData] = useState<JSONValue | null>(null);
  const [parentContextData, setParentContextData] = useState<JSONValue | null>(
    null,
  );
  const [contextError, setContextError] = useState<string | null>(null);
  const [lastPointerSegment, setLastPointerSegment] = useState<string | null>(
    null,
  );
  const [lastArrayIndex, setLastArrayIndex] = useState<number | null>(null);
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'));

  const loadContextData = useCallback(async (): Promise<void> => {
    if (fileUrl == null || fileUrl === '' || error == null) return;
    try {
      setLoadingContext(true);
      setContextError(null);
      setContextData(null);
      setParentContextData(null);
      setLastPointerSegment(null);
      setLastArrayIndex(null);
      clearExpiredCaches();
      const cachedJson = getCachedJson(fileUrl);
      let json: JSONValue;
      if (cachedJson != null) {
        json = cachedJson;
      } else {
        const fetchOptions: RequestInit = { credentials: 'omit' };
        const authHeaders = await buildAuthHeaders();
        if (authHeaders != null) {
          fetchOptions.headers = authHeaders;
        }
        const resp = await fetch(fileUrl, fetchOptions);
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }
        json = await resp.json();
        setCachedJson(fileUrl, json);
      }
      const segs = getPointerSegments(error.instancePath ?? '/');
      const lastSeg = segs.length > 0 ? segs[segs.length - 1] : null;
      const isIndex = lastSeg != null && /^\d+$/.test(lastSeg);
      const displayParentSegs = isIndex ? segs.slice(0, -2) : segs.slice(0, -1);
      const highlightKey = isIndex
        ? segs.length >= 2
          ? segs[segs.length - 2]
          : null
        : lastSeg;
      const parentPointer = '/' + displayParentSegs.join('/');
      const parentVal = resolveJsonPointer(json, parentPointer);
      const value = resolveJsonPointer(json, error.instancePath);
      setParentContextData((parentVal ?? null) as JSONValue | null);
      setLastPointerSegment(highlightKey);
      setLastArrayIndex(isIndex && lastSeg != null ? Number(lastSeg) : null);
      setContextData((value ?? null) as JSONValue | null);
    } catch (e) {
      let errorMessage = 'Failed to load data (possible CORS)';
      if (e instanceof Error) {
        errorMessage = e.message;
      }
      setContextError(errorMessage);
    } finally {
      setLoadingContext(false);
    }
  }, [fileUrl, error, buildAuthHeaders]);

  useEffect(() => {
    // Reset state whenever opening a new error
    if (open) {
      setLoadingContext(false);
      setContextData(null);
      setParentContextData(null);
      setContextError(null);
      setLastPointerSegment(null);
      setLastArrayIndex(null);
      void loadContextData();
    }
  }, [open, loadContextData]);

  useEffect(() => {
    if (!open) return;
    if (loadingContext) return;
    if (offendingRef.current != null) {
      offendingRef.current?.scrollIntoView?.({
        block: 'center',
        behavior: 'smooth',
      });
    }
  }, [
    open,
    loadingContext,
    parentContextData,
    contextData,
    lastPointerSegment,
    lastArrayIndex,
  ]);

  const [isEnum, isType, isPattern, isMinimum] = useMemo(() => {
    const keywordLower = (error?.keyword ?? '').toLowerCase();
    return [
      keywordLower === 'enum',
      keywordLower === 'type',
      keywordLower === 'pattern',
      keywordLower === 'minimum',
    ];
  }, [error?.keyword]);

  const formatJson = (value: unknown, spaces = 2): string => {
    try {
      return typeof value === 'string'
        ? JSON.stringify(value)
        : JSON.stringify(value, null, spaces);
    } catch {
      return String(value);
    }
  };

  const renderHighlightedObject = (
    obj: JSONValue,
    key: string | null,
    arrayIndex?: number | null,
  ): React.ReactElement => {
    if (obj == null || typeof obj !== 'object' || Array.isArray(obj)) {
      return (
        <Box component='pre' sx={highlightedPreSx}>
          {formatJson(obj, 2)}
        </Box>
      );
    }

    const entries = Object.entries(obj as Record<string, JSONValue>);

    return (
      <Box sx={highlightedContainerSx}>
        <Box sx={highlightedTitleSx}>
          <DataObjectIcon />
          <Typography sx={{ fontWeight: 'bold' }}>
            {error?.instancePath}
          </Typography>
        </Box>

        <Box sx={highlightedInnerSx}>
          {entries.map(([k, v]) => {
            const isHitProp = key != null && k === key;
            const rowProps =
              isHitProp && arrayIndex == null ? { ref: offendingRef } : {};
            return (
              <Tooltip
                key={k}
                title={
                  isHitProp
                    ? removePathFromMessage(
                        error?.message ?? '',
                        error?.instancePath ?? '',
                      ).replace(': ', '')
                    : ''
                }
                placement='top-start'
              >
                <Box {...rowProps} sx={entryRowSx(theme, isHitProp)}>
                  <Typography
                    component='span'
                    sx={keyTypographySx(theme, isHitProp)}
                  >
                    {k}:
                  </Typography>

                  {Array.isArray(v) ? (
                    <Box component='ol' sx={{ m: 0, pl: 2 }}>
                      {v.map((item, idx) => {
                        const isOffender =
                          isHitProp && arrayIndex != null && idx === arrayIndex;
                        return (
                          <Box
                            key={idx}
                            sx={listItemSx(theme, isOffender)}
                            component='li'
                            ref={isOffender ? offendingRef : undefined}
                          >
                            {formatJson(item, 0)}
                          </Box>
                        );
                      })}
                    </Box>
                  ) : (
                    <Typography component='span' sx={valueTypographySx}>
                      {formatJson(v, 0)}
                    </Typography>
                  )}
                </Box>
              </Tooltip>
            );
          })}
        </Box>
      </Box>
    );
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth='md'
      fullWidth
      PaperProps={{ sx: { backgroundColor: theme.palette.background.default } }}
      fullScreen={fullScreen}
    >
      <DialogTitle sx={dialogTitleSx}>
        <Typography variant='h6'>
          Validation error in {fileName}.json
        </Typography>
        <IconButton aria-label='close' onClick={onClose} size='small'>
          <CloseIcon fontSize='small' />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {error != null && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Box width={'100%'}>
                <Typography
                  variant='subtitle2'
                  sx={{ color: theme.palette.text.secondary }}
                >
                  Instance path
                </Typography>
                <code style={ValidationErrorPathStyles(theme)}>
                  {error.instancePath ?? '#'}
                </code>
              </Box>
              <Box width={'100%'}>
                <Typography
                  variant='subtitle2'
                  sx={{ color: theme.palette.text.secondary, width: '100%' }}
                >
                  Schema path
                </Typography>
                <code style={ValidationErrorPathStyles(theme)}>
                  {error.schemaPath ?? '#'}
                </code>
              </Box>
              <Box sx={{ mt: 2, width: '100%' }}>
                <Typography
                  variant='subtitle2'
                  sx={{ color: theme.palette.text.secondary, width: '100%' }}
                >
                  Error Message
                </Typography>
                <Box
                  sx={{
                    display: 'flex',
                    width: '100%',
                    alignItems: 'center',
                    gap: 2,
                    flexWrap: { xs: 'wrap', sm: 'nowrap' },
                  }}
                >
                  <Chip size='small' color='error' label={error.keyword} />
                  <Typography variant='subtitle1'>
                    {removePathFromMessage(
                      error.message,
                      error.instancePath,
                    ).replace(': ', '')}
                  </Typography>
                </Box>
              </Box>
            </Box>

            {fileUrl != null && fileUrl !== '' && (
              <Box sx={{ mt: 1 }}>
                <Box>
                  {loadingContext ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <CircularProgress size={18} />
                      <Typography variant='body2'>Loading…</Typography>
                    </Box>
                  ) : contextError != null && contextError !== '' ? (
                    <Typography variant='body2' color='error'>
                      {contextError}
                    </Typography>
                  ) : (
                    (contextData !== null || parentContextData !== null) && (
                      <Box
                        sx={{
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 1,
                        }}
                      >
                        {/* Issue highlight */}
                        {(() => {
                          const missingKey = getMissingKeyFromMessage(
                            error.message,
                          );
                          const keywordLower = (
                            error.keyword ?? ''
                          ).toLowerCase();
                          const shouldHighlightParent =
                            (isEnum || isType || isPattern || isMinimum) &&
                            lastPointerSegment != null &&
                            parentContextData != null;
                          const isRequiredErrorType =
                            keywordLower === 'required' ||
                            (missingKey != null && missingKey !== '');
                          const shouldShowContext =
                            shouldHighlightParent || isRequiredErrorType;

                          if (shouldShowContext) {
                            if (isRequiredErrorType) {
                              return (
                                <Box
                                  sx={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: 0.75,
                                  }}
                                >
                                  {missingKey != null && missingKey !== '' && (
                                    <Box
                                      ref={offendingRef}
                                      sx={{
                                        m: 0,
                                        p: 1,
                                        borderRadius: 1,
                                        backgroundColor: 'rgba(244,67,54,0.08)',
                                        borderLeft: `3px solid ${theme.palette.error.main}`,
                                        fontFamily: 'monospace',
                                      }}
                                    >
                                      <Typography
                                        component='span'
                                        sx={{
                                          fontFamily: 'inherit',
                                          fontWeight: 700,
                                          color: theme.palette.error.main,
                                        }}
                                      >
                                        &quot;{missingKey}&quot;:
                                      </Typography>{' '}
                                      <Typography
                                        component='span'
                                        sx={{
                                          fontFamily: 'inherit',
                                          fontStyle: 'italic',
                                        }}
                                      >
                                        &lt;missing&gt;
                                      </Typography>
                                    </Box>
                                  )}
                                  {renderHighlightedObject(
                                    parentContextData as JSONValue,
                                    null,
                                    null,
                                  )}
                                </Box>
                              );
                            }
                            return renderHighlightedObject(
                              parentContextData as JSONValue,
                              lastPointerSegment ?? null,
                              lastArrayIndex,
                            );
                          }

                          return (
                            <Box
                              component='pre'
                              ref={offendingRef}
                              sx={outlinePreSx}
                            >
                              {formatJson(contextData, 2)}
                            </Box>
                          );
                        })()}
                      </Box>
                    )
                  )}
                </Box>
                <Typography
                  variant='body2'
                  color='text.secondary'
                  sx={{ mt: 1 }}
                >
                  Source:{' '}
                  <Link
                    href={fileUrl}
                    target='_blank'
                    rel='noopener noreferrer'
                  >
                    {fileUrl}
                  </Link>
                </Typography>
              </Box>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color='inherit'>
          Close
        </Button>
        {fileUrl != null && fileUrl !== '' && (
          <Button
            color='inherit'
            endIcon={<OpenInNew />}
            component={Link}
            href={fileUrl}
            target='_blank'
            rel='noopener noreferrer'
          >
            Open file
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

export default ErrorDetailsDialog;
