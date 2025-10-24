import { Box, Typography, useTheme } from '@mui/material';
import { useRef } from 'react';
import Draggable from 'react-draggable';
import { useTranslation } from 'react-i18next';
import { type MapStopElement } from '../MapElement';

interface SelectedRoutesStopsPanelProps {
  filteredRoutes: string[];
  selectedRouteStops: MapStopElement[];
  selectedStopId: string | null;
  focusStopFromPanel: (stop: MapStopElement) => void;
}

export const SelectedRoutesStopsPanel = (
  props: React.PropsWithChildren<SelectedRoutesStopsPanelProps>,
): JSX.Element => {
  const {
    filteredRoutes,
    selectedRouteStops,
    selectedStopId,
    focusStopFromPanel,
  } = props;
  const theme = useTheme();
  const routeStopsPanelNodeRef = useRef<HTMLDivElement | null>(null);
  const { t } = useTranslation('feeds');
  return (
    <Draggable
      nodeRef={routeStopsPanelNodeRef}
      handle='.drag-handle'
      bounds='parent'
    >
      <Box
        ref={routeStopsPanelNodeRef}
        sx={{
          position: 'absolute',
          right: '10px',
          top: '25%',
          height: '50%',
          width: 250,
          transform: 'translateY(-0%)',
          zIndex: 1000,
          bgcolor: theme.palette.background.default,
          borderRadius: '12px',
          boxShadow: '1px 1px 8px rgba(0,0,0,0.25)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <Box
          sx={{
            p: 1.5,
            borderBottom: `1px solid ${theme.palette.divider}`,
            cursor: 'move',
          }}
          className='drag-handle'
        >
          <Typography variant='subtitle2' sx={{ fontWeight: 600 }}>
            {t('selectedRouteStops.title', {
              count: filteredRoutes.length,
            })}{' '}
            ({selectedRouteStops.length})
          </Typography>
          <Typography
            variant='caption'
            sx={{ color: theme.palette.text.secondary }}
          >
            {t('selectedRouteStops.routeIds', {
              count: filteredRoutes.length,
            })}
            : {filteredRoutes.join(' | ')}
          </Typography>
        </Box>
        <Box sx={{ flex: 1, overflowY: 'auto', p: 1 }}>
          {selectedRouteStops.map((s) => {
            const isActive = selectedStopId === s.stopId;
            return (
              <Box
                key={s.stopId}
                role='button'
                tabIndex={0}
                aria-selected={isActive ? 'true' : 'false'}
                onClick={() => {
                  focusStopFromPanel(s);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') focusStopFromPanel(s);
                }}
                sx={{
                  py: 0.9,
                  px: 1.1,
                  mb: 0.5,
                  borderRadius: '10px',
                  border: isActive
                    ? `2px solid ${theme.palette.primary.main}`
                    : `1px solid ${theme.palette.divider}`,
                  backgroundColor: isActive
                    ? theme.palette.action.selected
                    : 'transparent',
                  transition:
                    'background-color 120ms ease, border-color 120ms ease, box-shadow 120ms ease',
                  cursor: 'pointer',
                  '&:hover': {
                    backgroundColor: theme.palette.action.hover,
                  },
                  boxShadow: isActive
                    ? '0 0 0 2px rgba(0,0,0,0.06) inset'
                    : 'none',
                }}
              >
                <Typography
                  variant='body2'
                  sx={{ fontWeight: 700, lineHeight: 1.2 }}
                >
                  {s.name}
                </Typography>
                <Typography
                  variant='caption'
                  sx={{ color: theme.palette.text.secondary }}
                >
                  {t('selectedRouteStops.stopId')} {s.stopId}
                </Typography>
              </Box>
            );
          })}
        </Box>
      </Box>
    </Draggable>
  );
};
