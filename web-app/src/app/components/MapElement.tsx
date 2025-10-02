import * as React from 'react';
import 'leaflet/dist/leaflet.css';
import { Box, Typography, useTheme } from '@mui/material';
import {
  renderLocationTypeIcon,
  renderRouteTypeIcon,
} from '../constants/RouteTypes';
import { useTranslation } from 'react-i18next';

export interface BaseMapElement {
  isStop: boolean;
  name: string;
}

export interface MapRouteElement extends BaseMapElement {
  routeType: number;
  routeColor: string;
  routeTextColor: string;
  routeId: string;
}

export interface MapStopElement extends BaseMapElement {
  locationType: number;
  stopId: string;
  stopLat: number;
  stopLon: number;
}

export type MapElementType = MapRouteElement | MapStopElement;

export interface MapElementProps {
  mapElements: MapElementType[];
  dataDisplayLimit?: number;
}

export const MapElement = (
  props: React.PropsWithChildren<MapElementProps>,
): JSX.Element => {
  const theme = useTheme();
  const { t, i18n } = useTranslation('feeds', { useSuspense: false });
  if (!i18n.isInitialized || !i18n.hasResourceBundle(i18n.language, 'feeds')) {
    // render fallback (no t()) to avoid updates during render
    return <></>;
  }

  const limit = props.dataDisplayLimit ?? 10;
  const formatSet = new Set<string>();
  const formattedElements: MapElementType[] = [];

  for (const element of props.mapElements) {
    if (formatSet.has(element.name)) continue;
    formattedElements.push(element);
    formatSet.add(element.name);
    if (formattedElements.length >= limit) break; // exact cap
  }
  const uniqueElementNames = new Set(
    props.mapElements.map((element) => element.name),
  );
  const elementLeftover = uniqueElementNames.size - formattedElements.length;

  const renderRouteMapElement = (element: MapRouteElement): JSX.Element => {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          color:
            element.routeTextColor !== ''
              ? '#' + element.routeTextColor
              : theme.map.routeTextColor,
          background:
            element.routeColor !== ''
              ? '#' + element.routeColor
              : theme.map.routeColor,
          padding: '5px',
          borderRadius: '5px',
        }}
      >
        {renderRouteTypeIcon(
          element.routeType != null ? element.routeType.toString() : '0',
          element.routeTextColor !== ''
            ? '#' + element.routeTextColor
            : theme.map.routeTextColor,
        )}

        <Typography gutterBottom sx={{ color: 'inherit', fontSize: 14, m: 0 }}>
          {element.routeId} - {element.name}
        </Typography>
      </Box>
    );
  };

  const renderStopMapElement = (
    element: MapStopElement,
    iconColor: string,
  ): JSX.Element => {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          padding: '5px',
          borderRadius: '5px',
        }}
      >
        {renderLocationTypeIcon(
          element.locationType != null ? element.locationType.toString() : '0',
          iconColor,
        )}

        <Typography gutterBottom sx={{ color: 'inherit', fontSize: 14, m: 0 }}>
          {element.stopId} - {element.name}
        </Typography>
      </Box>
    );
  };

  return (
    <Box
      sx={{
        position: 'absolute',
        top: '10px',
        left: '10px',
        zIndex: 1000,
      }}
    >
      {formattedElements.map((element, index) => {
        return (
          <Box
            key={index}
            sx={{
              background: theme.palette.background.default,
              borderRadius: '10px',
              boxShadow: '1px 1px 5px 1px rgba(0,0,0,0.2)',
              padding: '10px',
              my: 2,
              overflow: 'hidden',
              width: '250px',
            }}
          >
            <Typography variant='body1' sx={{ mb: '4px', fontSize: '12px' }}>
              {element.isStop ? 'Stop' : 'Route'}
            </Typography>
            {element.isStop ? (
              <>
                {renderStopMapElement(
                  element as MapStopElement,
                  theme.palette.text.primary,
                )}
              </>
            ) : (
              <>{renderRouteMapElement(element as MapRouteElement)}</>
            )}
          </Box>
        );
      })}
      {elementLeftover > 0 && (
        <Box
          sx={{
            background: theme.palette.background.default,
            borderRadius: '10px',
            boxShadow: '1px 1px 5px 1px rgba(0,0,0,0.2)',
            padding: '10px',
            my: 2,
            overflow: 'hidden',
            width: '250px',
          }}
        >
          <Typography variant='body1' sx={{ mb: '4px', fontSize: '12px' }}>
            {t('andMoreElements', { count: elementLeftover })}
          </Typography>
        </Box>
      )}
    </Box>
  );
};
