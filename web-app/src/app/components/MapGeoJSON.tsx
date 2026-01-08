'use client';

import * as React from 'react';
import MapGL, {
  NavigationControl,
  Source,
  Layer,
  Popup,
} from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { type LatLngExpression } from 'leaflet';
import { useTranslations } from 'next-intl';
import { PopupTable } from './PopupTable';
import { useTheme } from '@mui/material/styles';
import { Box, Typography, Tooltip } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { getBoundsFromCoordinates } from './GtfsVisualizationMap.functions';

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

export interface GeoJSONDataGBFS extends GeoJSONData {
  extracted_at: string;
  extraction_url: string;
}

export interface MapProps {
  geoJSONData: GeoJSONData | null;
  polygon: LatLngExpression[];
  displayMapDetails?: boolean;
}

export const MapGeoJSON = (
  props: React.PropsWithChildren<MapProps>,
): JSX.Element => {
  const theme = useTheme();
  const t = useTranslations('feeds');
  const { geoJSONData, displayMapDetails = true } = props;
  const [ready, setReady] = React.useState(false);
  const [popupInfo, setPopupInfo] = React.useState<any | null>(null);

  React.useEffect(() => {
    setReady(true);
  }, []);

  const bounds = React.useMemo(() => {
    return getBoundsFromCoordinates(props.polygon as any);
  }, [props.polygon]);

  if (!displayMapDetails) {
    geoJSONData?.features?.forEach((feature) => {
      feature.properties.color = 'rgba(127, 0, 0, 1.0)';
      delete feature.properties.stops_in_area;
      delete feature.properties.stops_in_area_coverage;
    });
  }

  if (!ready) {
    return (
      <Box
        style={{ minHeight: '400px', height: '100%', width: '100%' }}
        data-testid='map-geojson-loading'
      />
    );
  }

  return (
    <Box
      sx={{
        minHeight: '400px',
        height: '100%',
        position: 'relative',
      }}
    >
      <MapGL
        initialViewState={{
          bounds,
          fitBoundsOptions: { padding: 50 },
        }}
        style={{ minHeight: '400px', height: '100%', width: '100%' }}
        data-testid='geojson-map'
        interactiveLayerIds={['geojson-fill']}
        onClick={(e) => {
          const feature = e.features?.[0];
          if (feature != null) {
            setPopupInfo({
              lngLat: e.lngLat,
              properties: feature.properties,
            });
          }
        }}
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
        <Source id='geojson-source' type='geojson' data={geoJSONData as any}>
          <Layer
            id='geojson-fill'
            type='fill'
            paint={{
              'fill-color': [
                'coalesce',
                ['get', 'color'],
                theme.palette.primary.main,
              ],
              'fill-opacity': 0.3,
            }}
          />
          <Layer
            id='geojson-outline'
            type='line'
            paint={{
              'line-color': [
                'coalesce',
                ['get', 'color'],
                theme.palette.primary.main,
              ],
              'line-width': 2,
            }}
          />
        </Source>
        <NavigationControl position='top-right' />
        {popupInfo != null && (
          <Popup
            longitude={popupInfo.lngLat.lng}
            latitude={popupInfo.lngLat.lat}
            anchor='bottom'
            onClose={() => {
              setPopupInfo(null);
            }}
            closeOnClick={false}
          >
            <PopupTable properties={popupInfo.properties} theme={theme} />
          </Popup>
        )}
      </MapGL>
      {props.geoJSONData !== null && displayMapDetails && (
        <Box
          sx={{
            position: 'absolute',
            bottom: 20,
            right: 16,
            background: theme.palette.background.paper,
            padding: 1,
            borderRadius: 2,
            boxShadow: 3,
            maxWidth: 175,
            zIndex: 1000,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Typography style={{ fontSize: '0.85rem', fontWeight: 800 }}>
              {t('heatmapIntensity')}
            </Typography>
            <Tooltip
              title={
                <React.Fragment>
                  <Typography sx={{ fontWeight: 800 }}>
                    <strong>{t('heatmapExplanationTitle')}</strong>
                  </Typography>
                  <div>
                    {t.rich('heatmapExplanationContent', {
                      code: (chunks) => <code>{chunks}</code>,
                    })}
                  </div>
                </React.Fragment>
              }
            >
              <InfoOutlinedIcon
                sx={{
                  fontSize: '16px',
                  color: theme.palette.text.secondary,
                  cursor: 'pointer',
                }}
              />
            </Tooltip>
          </Box>
          <Box
            sx={{
              width: '100%',
              height: '16px',
              background: `linear-gradient(to right, #fb8c58, #7f0000)`,
              marginTop: 2,
              marginBottom: 1,
              borderRadius: 1,
            }}
          />
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '0.75rem',
              gap: 2,
              color: theme.palette.text.secondary,
            }}
          >
            <span>{t('heatmapLower')}</span>
            <span>{t('heatmapHigher')}</span>
          </Box>
        </Box>
      )}
    </Box>
  );
};
