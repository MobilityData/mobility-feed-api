import * as React from 'react';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import {
  type LatLngBoundsExpression,
  type LatLngExpression,
  type LeafletMouseEvent,
} from 'leaflet';
import { PopupTable } from './PopupTable';
import { createRoot } from 'react-dom/client';
import { useTheme } from '@mui/material/styles';
import { ThemeModeEnum } from '../Theme';
import { Box } from '@mui/material';

export interface GeoJSONData {
  type: 'FeatureCollection' | 'Feature' | 'GeometryCollection';
  features?: Array<{
    type: 'Feature';
    geometry: {
      type: 'Point' | 'Polygon' | 'LineString' | 'MultiPolygon';
      coordinates: number[][] | number[][][];
    };
    properties: Record<string, string | number>;
  }>;
}

export interface MapProps {
  geoJSONData: GeoJSONData | null;
  polygon: LatLngExpression[];
}

export const MapGeoJSON = (
  props: React.PropsWithChildren<MapProps>,
): JSX.Element => {
  const theme = useTheme();

  const handleFeatureClick = (
    e: LeafletMouseEvent,
    previousColor: string,
  ): void => {
    const currentSelection = e.target as L.Path;
    currentSelection.setStyle({ color: theme.palette.primary.main });
    currentSelection.on('popupclose', () => {
      currentSelection.setStyle({ color: previousColor });
    });
  };

  const mapTiles =
    theme.palette.mode === ThemeModeEnum.dark
      ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
      : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';

  return (
    <Box
      sx={{
        '.leaflet-popup-content-wrapper': {
          background: theme.palette.background.default,
        },
        '.leaflet-popup-tip': {
          background: theme.palette.background.default,
        },
        minHeight: '400px',
        height: '100%',
      }}
    >
      <MapContainer
        bounds={props.polygon as LatLngBoundsExpression}
        zoom={8}
        style={{
          height: '100%',
        }}
        data-testid='geojson-map'
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url={mapTiles}
        />
        {props.geoJSONData !== null && (
          <GeoJSON
            data={props.geoJSONData}
            onEachFeature={(feature, layer) => {
              const container = document.createElement('div');
              container.style.background = theme.palette.background.default;
              const root = createRoot(container);
              root.render(
                <PopupTable properties={feature.properties} theme={theme} />,
              );
              layer.bindPopup(container);

              // Handle feature clicks
              layer.on({
                click: (e) => {
                  handleFeatureClick(
                    e,
                    feature?.properties?.color ?? '#3388ff',
                  );
                },
              });
            }}
            style={(feature) => ({
              weight: 3,
              opacity: 1,
              color: feature?.properties?.color ?? '#3388ff',
              fillOpacity: 0.3,
            })}
          />
        )}
      </MapContainer>
    </Box>
  );
};
