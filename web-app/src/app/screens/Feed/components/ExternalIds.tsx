'use client';

import React from 'react';
import {
  Box,
  IconButton,
  Tooltip,
  Typography,
  Link,
  Button,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { type components } from '../../../services/feeds/types';
import {
  externalIdSourceMap,
  filterFeedExternalIdsToSourceMap,
} from '../../../utils/externalIds';
import { useTranslations } from 'next-intl';

type ExternalIdInfo = components['schemas']['ExternalIds'];

export interface ExternalIdsProps {
  externalIds: ExternalIdInfo | undefined;
}

export default function ExternalIds({
  externalIds,
}: ExternalIdsProps): React.ReactElement | null {
  const t = useTranslations('feeds');
  if (externalIds == null || externalIds.length === 0) return null;
  const filteredExternalIds = filterFeedExternalIdsToSourceMap(externalIds);
  if (filteredExternalIds.length === 0) return null;
  return (
    <Box sx={{ mt: 2, mb: 0 }}>
      <Typography
        variant='subtitle2'
        sx={{ fontWeight: 700, color: 'text.secondary' }}
      >
        External IDs
      </Typography>
      <Box sx={{ mt: 0.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
        {filteredExternalIds.map((externalId, idx) => {
          const src = externalId.source.toLowerCase();
          const info = externalIdSourceMap[src];
          return (
            <Box
              key={idx}
              sx={{ display: 'flex', gap: 1, alignItems: 'center' }}
            >
              {info.docsUrl != null ? (
                <Button
                  variant='text'
                  sx={{
                    fontWeight: 700,
                    minWidth: 'auto',
                    color: 'text.primary',
                    textTransform: 'none',
                    p: 0,
                    px: 1.5,
                    ml: -1.5,
                    fontSize: 'medium',
                  }}
                  component={Link}
                  href={info.docsUrl}
                  target='_blank'
                  rel='noopener noreferrer'
                >
                  {info?.label ?? externalId.source}
                </Button>
              ) : (
                <Typography
                  sx={{
                    fontWeight: 700,
                    minWidth: 'auto',
                    color: 'text.primary',
                    pr: 1.5,
                    fontSize: 'medium',
                  }}
                >
                  {info?.label ?? externalId.source}
                </Typography>
              )}

              <Typography
                variant='body1'
                sx={{ wordBreak: 'break-all', lineHeight: 1.2 }}
              >
                {externalId.external_id}
              </Typography>
              <Tooltip title={t(info.translationKey)} placement='top'>
                {info.docsUrl == null ? (
                  <InfoOutlinedIcon
                    sx={{
                      p: '5px',
                      boxSizing: 'content-box',
                      fontSize: '1.125rem',
                    }}
                  />
                ) : (
                  <IconButton
                    size='small'
                    color='primary'
                    component={Link}
                    href={info.docsUrl}
                    target='_blank'
                    rel='noopener noreferrer'
                  >
                    <InfoOutlinedIcon fontSize='inherit' />
                  </IconButton>
                )}
              </Tooltip>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
