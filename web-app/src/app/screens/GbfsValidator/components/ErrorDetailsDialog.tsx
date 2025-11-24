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
  Typography,
  useTheme,
} from '@mui/material';
import { OpenInNew } from '@mui/icons-material';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { type components } from '../../../services/feeds/gbfs-validator-types';
import {
  resolveJsonPointer,
  getPointerSegments,
  getMissingKeyFromMessage,
  type JSONValue,
} from '../errorDetailsUtils';

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

  useEffect(() => {
    // Reset state whenever opening a new error
    if (open) {
      setLoadingContext(false);
      setContextData(null);
      setParentContextData(null);
      setContextError(null);
      setLastPointerSegment(null);
      setLastArrayIndex(null);
    }
  }, [open, error]);

  useEffect(() => {
    if (!open) return;
    if (loadingContext) return;
    if (offendingRef.current) {
      try {
        offendingRef.current.scrollIntoView({ block: 'center', behavior: 'smooth' });
      } catch {}
    }
  }, [open, loadingContext, parentContextData, contextData, lastPointerSegment, lastArrayIndex]);

  const isEnum = useMemo(
    () => (error?.keyword ?? '').toLowerCase() === 'enum',
    [error?.keyword],
  );

  const loadContextData = async (): Promise<void> => {
    if (!fileUrl || !error) return;
    try {
      setLoadingContext(true);
      setContextError(null);
      setContextData(null);
      setParentContextData(null);
      setLastPointerSegment(null);
      setLastArrayIndex(null);
      const resp = await fetch(fileUrl, { credentials: 'omit' });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const json: JSONValue = await resp.json();
      const segs = getPointerSegments(error.instancePath || '/');
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
    } catch (e: any) {
      setContextError(e?.message ?? 'Failed to load data (possible CORS)');
    } finally {
      setLoadingContext(false);
    }
  };

  const renderHighlightedObject = (
    obj: JSONValue,
    key: string | null,
    arrayIndex?: number | null,
  ): React.ReactElement => {
    if (obj == null || typeof obj !== 'object' || Array.isArray(obj)) {
      return (
        <Box
          component='pre'
          sx={{
            m: 0,
            p: 1,
            borderRadius: 1,
            backgroundColor: theme.palette.action.hover,
            maxHeight: 300,
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontFamily: 'monospace',
          }}
        >
          {(() => {
            try {
              return JSON.stringify(obj, null, 2);
            } catch {
              return String(obj);
            }
          })()}
        </Box>
      );
    }
    const entries = Object.entries(obj as Record<string, JSONValue>);
    return (
      <Box
        sx={{
          m: 0,
          p: 1,
          borderRadius: 1,
          backgroundColor: theme.palette.action.hover,
          maxHeight: 300,
          overflow: 'auto',
          fontFamily: 'monospace',
        }}
      >
        {entries.map(([k, v]) => {
          const isHitProp = key != null && k === key;
          const rowProps = isHitProp && arrayIndex == null ? { ref: offendingRef } : {};
          return (
            <Box
              key={k}
              {...rowProps}
              sx={{
                display: 'flex',
                gap: 1,
                alignItems: 'flex-start',
                px: 0.5,
                borderLeft: isHitProp ? '3px solid' : undefined,
                borderColor: isHitProp ? theme.palette.error.main : undefined,
                backgroundColor: isHitProp ? 'rgba(244,67,54,0.08)' : undefined,
                borderRadius: 0.5,
              }}
            >
              <Typography
                component='span'
                sx={{
                  fontFamily: 'inherit',
                  fontWeight: isHitProp ? 700 : 400,
                  color: isHitProp ? theme.palette.error.main : 'inherit',
                }}
              >
                {k}:
              </Typography>
              {Array.isArray(v) ? (
                <Box component='ol' sx={{ m: 0, pl: 2 }}>
                  {v.map((item, idx) => {
                    const isOffender = isHitProp && arrayIndex != null && idx === arrayIndex;
                    return (
                      <Box
                        key={idx}
                        component='li'
                        ref={isOffender ? offendingRef : undefined}
                        sx={{
                          backgroundColor: isOffender ? 'rgba(244,67,54,0.08)' : undefined,
                          borderLeft: isOffender ? '3px solid' : undefined,
                          borderColor: isOffender ? theme.palette.error.main : undefined,
                          pl: isOffender ? 1 : 0,
                          borderRadius: 0.5,
                          wordBreak: 'break-word',
                        }}
                      >
                        {(() => {
                          try {
                            return typeof item === 'string'
                              ? JSON.stringify(item)
                              : JSON.stringify(item, null, 0);
                          } catch {
                            return String(item);
                          }
                        })()}
                      </Box>
                    );
                  })}
                </Box>
              ) : (
                <Typography
                  component='span'
                  sx={{ fontFamily: 'inherit', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
                >
                  {(() => {
                    try {
                      return typeof v === 'string' ? JSON.stringify(v) : JSON.stringify(v, null, 0);
                    } catch {
                      return String(v);
                    }
                  })()}
                </Typography>
              )}
            </Box>
          );
        })}
      </Box>
    );
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth='md' fullWidth>
      <DialogTitle>Validation error in {fileName}.json</DialogTitle>
      <DialogContent dividers>
        {error && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
            <Box>
              <Typography variant='subtitle2'>Message</Typography>
              <Typography>{error.message}</Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
              <Box>
                <Typography variant='subtitle2'>Keyword</Typography>
                <Chip size='small' color='error' label={error.keyword} />
              </Box>
              <Box>
                <Typography variant='subtitle2'>Instance path</Typography>
                <Typography component='div'>
                  <code style={{
                    display: 'inline-block',
                    padding: '1px 6px',
                    borderRadius: 4,
                    background: theme.palette.action.hover,
                    border: `1px solid ${theme.palette.divider}`,
                  }}>
                    {error.instancePath || '#'}
                  </code>
                </Typography>
              </Box>
              <Box>
                <Typography variant='subtitle2'>Schema path</Typography>
                <Typography component='div'>
                  <code>{error.schemaPath}</code>
                </Typography>
              </Box>
            </Box>
            {fileUrl && (
              <Box sx={{ mt: 1 }}>
                <Typography variant='subtitle2' sx={{ mb: 0.5 }}>
                  Data context
                </Typography>
                <Typography variant='body2' color='text.secondary' sx={{ mb: 1 }}>
                  Source:{' '}
                  <Link href={fileUrl} target='_blank' rel='noopener noreferrer'>
                    {fileUrl}
                  </Link>
                </Typography>
                <Box>
                  {loadingContext ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <CircularProgress size={18} />
                      <Typography variant='body2'>Loading…</Typography>
                    </Box>
                  ) : contextError ? (
                    <Typography variant='body2' color='error'>
                      {contextError}
                    </Typography>
                  ) : contextData !== null || parentContextData !== null ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      {/* Issue highlight */}
                      {(() => {
                        const missingKey = getMissingKeyFromMessage(error.message);
                        if ((isEnum && lastPointerSegment != null && parentContextData != null) || error.keyword.toLowerCase() === 'required' || missingKey) {
                          if (error.keyword.toLowerCase() === 'required' || missingKey) {
                            return (
                              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                                {missingKey && (
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
                                    <Typography component='span' sx={{ fontFamily: 'inherit', fontWeight: 700, color: theme.palette.error.main }}>
                                      &quot;{missingKey}&quot;:
                                    </Typography>{' '}
                                    <Typography component='span' sx={{ fontFamily: 'inherit', fontStyle: 'italic' }}>&lt;missing&gt;</Typography>
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
                            sx={{
                              m: 0,
                              p: 1,
                              borderRadius: 1,
                              backgroundColor: theme.palette.action.hover,
                              maxHeight: 300,
                              overflow: 'auto',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                              outline: `2px solid ${theme.palette.error.main}`,
                              outlineOffset: '-2px',
                            }}
                          >
                            {(() => {
                              try {
                                return JSON.stringify(contextData, null, 2);
                              } catch {
                                return String(contextData);
                              }
                            })()}
                          </Box>
                        );
                      })()}
                    </Box>
                  ) : (
                    <Button variant='outlined' size='small' onClick={async () => { await loadContextData(); }}>
                      Load data at path
                    </Button>
                  )}
                </Box>
              </Box>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color='inherit'>
          Close
        </Button>
        {fileUrl && (
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
