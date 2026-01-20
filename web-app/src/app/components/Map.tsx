'use client';

import * as React from 'react';
import MapGL, {
  NavigationControl,
  Source,
  Layer,
  MapProvider,
} from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { type LatLngTuple } from 'leaflet';
import { useTheme } from '@mui/material/styles';
import { Box } from '@mui/material';
import { getBoundsFromCoordinates } from './GtfsVisualizationMap.functions';

export interface MapProps {
  polygon: LatLngTuple[];
}

export const Map = (props: React.PropsWithChildren<MapProps>): JSX.Element => {
  const theme = useTheme();
  const [ready, setReady] = React.useState(false);

  React.useEffect(() => {
    setReady(true);
  }, []);

  const bounds = React.useMemo(() => {
    return getBoundsFromCoordinates(props.polygon);
  }, [props.polygon]);

  if (!ready) {
    return (
      <Box
        style={{ minHeight: '400px', height: '100%', width: '100%' }}
        data-testid='map-loading'
      />
    );
  }
  // Convert LatLngExpression[] to GeoJSON ring for Source
  const coordinates = props.polygon.map((p) => {
    return [p[1], p[0]];
  });

  // Ensure it's a closed ring for a polygon
  if (
    coordinates.length > 0 &&
    (coordinates[0][0] !== coordinates[coordinates.length - 1][0] ||
      coordinates[0][1] !== coordinates[coordinates.length - 1][1])
  ) {
    coordinates.push(coordinates[0]);
  }

  const polygonGeoJSON: GeoJSON.Feature<GeoJSON.Polygon> = {
    type: 'Feature',
    geometry: {
      type: 'Polygon',
      coordinates: [coordinates],
    },
    properties: {},
  };

  return (
    <MapProvider>
      <Box sx={{ position: 'relative', width: '100%', height: '100%' }}>
        <MapGL
          initialViewState={{
            bounds,
            fitBoundsOptions: { padding: 50 },
          }}
          style={{ minHeight: '400px', height: '100%', width: '100%' }}
          mapStyle={{
            version: 8,
            sources: {
              'raster-tiles': {
                type: 'raster',
                tiles: [theme.map.basemapTileUrl],
                tileSize: 256,
                attribution:
                  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
              },
            },
            layers: [
              {
                id: 'basemap',
                type: 'raster',
                source: 'raster-tiles',
                minzoom: 0,
                maxzoom: 22,
              },
            ],
          }}
        >
          <Source id='polygon-source' type='geojson' data={polygonGeoJSON}>
            <Layer
              id='polygon-fill'
              type='fill'
              paint={{
                'fill-color': theme.palette.primary.main,
                'fill-opacity': 0.2,
              }}
            />
            <Layer
              id='polygon-outline'
              type='line'
              paint={{
                'line-color': theme.palette.primary.main,
                'line-width': 2,
              }}
            />
          </Source>
          <NavigationControl position='top-right' />
        </MapGL>
      </Box>
    </MapProvider>
  );
};
