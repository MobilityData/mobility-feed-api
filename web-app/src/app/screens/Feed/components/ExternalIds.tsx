import React from 'react';
import { Box, IconButton, Tooltip, Typography } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { type components } from '../../../services/feeds/types';
import {
  externalIdSourceMap,
  filterFeedExternalIdsToSourceMap,
} from '../../../utils/externalIds';
import { useTranslation } from 'react-i18next';

type ExternalIdInfo = components['schemas']['ExternalIds'];

export interface ExternalIdsProps {
  externalIds: ExternalIdInfo | undefined;
}

export default function ExternalIds({
  externalIds,
}: ExternalIdsProps): React.ReactElement | null {
  const { t } = useTranslation('feeds');
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
            <Box key={idx} sx={{ display: 'flex', gap: 1 }}>
              <Typography
                variant='body1'
                sx={{ fontWeight: 700, minWidth: 50 }}
              >
                {info?.label ?? externalId.source}
              </Typography>
              <Typography variant='body1' sx={{ wordBreak: 'break-all' }}>
                {externalId.external_id}
              </Typography>
              <Tooltip title={t(info.translationKey)} placement='top'>
                <IconButton size='small'>
                  <InfoOutlinedIcon fontSize='inherit' />
                </IconButton>
              </Tooltip>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
