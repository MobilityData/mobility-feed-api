import * as React from 'react';
import 'leaflet/dist/leaflet.css';
import { Box, Typography, useTheme } from '@mui/material';
import {
  locationTypesMapping,
  type RouteTypeMetadata,
  routeTypesMapping,
} from '../constants/RouteTypes';

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
}

export type MapElement = MapRouteElement | MapStopElement;

export interface MapElementProps {
  mapElements: MapElement[];
}

export const MapElement = (
  props: React.PropsWithChildren<MapElementProps>,
): JSX.Element => {
  const theme = useTheme();
  const formatSet = new Set();
  const formattedElements: MapElement[] = [];

  props.mapElements.forEach((element) => {
    if (!formatSet.has(element.name)) {
      formattedElements.push(element);
    }
    formatSet.add(element.name);
  });

  // TODO: duplicate
  const renderRouteTypeIcon = (
    routeTypeMetadata: RouteTypeMetadata,
    routeColorText: string,
  ): JSX.Element | null => {
    // The route type could be out of specs (e.g. google route types), so we may not have an icon.
    if (!routeTypeMetadata || !routeTypeMetadata.icon) {
       // Optionally render a default icon or return null
       return null;
    }
    const { icon: Icon } = routeTypeMetadata;
    return <Icon style={{ color:  routeColorText, fontSize: 20 }} />;
  };

  const renderRouteMapElement = (element: MapRouteElement): JSX.Element => {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          color: element.routeTextColor
            ? '#' + element.routeTextColor
            : '000000',
          background: element.routeColor ? '#' + element.routeColor : 'ffffff',
          padding: '5px',
          borderRadius: '5px',
        }}
      >
        {renderRouteTypeIcon(
          routeTypesMapping[element.routeType?.toString() || '0'],
          element.routeTextColor ? '#' + element.routeTextColor : '#000000',
        )}

        <Typography gutterBottom sx={{ color: 'inherit', fontSize: 14, m: 0 }}>
          {element.routeId} - {element.name}
        </Typography>
      </Box>
    );
  };

  const renderStopMapElement = (element: MapStopElement, iconColor: string): JSX.Element => {
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
        {renderRouteTypeIcon(
          locationTypesMapping[element.locationType?.toString() || '0'],
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
              <>{renderStopMapElement(element as MapStopElement, theme.palette.text.primary)}</>
            ) : (
              <>{renderRouteMapElement(element as MapRouteElement)}</>
            )}
          </Box>
        );
      })}
    </Box>
  );
};
