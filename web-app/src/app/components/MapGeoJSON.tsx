import * as React from 'react';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import {
  type LatLngBoundsExpression,
  type LatLngExpression,
  type LeafletMouseEvent,
} from 'leaflet';
import { Trans, useTranslation } from 'react-i18next';
import { PopupTable } from './PopupTable';
import { createRoot } from 'react-dom/client';
import { useTheme } from '@mui/material/styles';
import { ThemeModeEnum } from '../Theme';
import { Box, Typography, Tooltip } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

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
  const { t } = useTranslation('feeds');
  const { geoJSONData, displayMapDetails = true } = props;
  const bounds = React.useMemo(() => {
    return props.polygon.length > 0
      ? (props.polygon as LatLngBoundsExpression)
      : ([
          [0, 0],
          [0, 0],
        ] as LatLngBoundsExpression);
  }, [props.polygon]);

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
        bounds={bounds}
        zoom={8}
        style={{ minHeight: '400px', height: '100%' }}
        data-testid='geojson-map'
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url={mapTiles}
        />
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
                      {' '}
                      <Trans
                        i18nKey={t('heatmapExplanationContent')}
                        components={{ code: <code /> }}
                      />
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

        {geoJSONData !== null && (
          <GeoJSON
            data={geoJSONData}
            onEachFeature={(feature, layer) => {
              const container = document.createElement('div');
              container.style.background = theme.palette.background.default;
              const root = createRoot(container);
              const featureProperties = feature?.properties ?? {};
              if (!displayMapDetails) {
                delete featureProperties.stops_in_area;
                delete featureProperties.stops_in_area_coverage;
                featureProperties.color = 'rgba(127, 0, 0, 1.0)';
              }
              root.render(
                <PopupTable properties={featureProperties} theme={theme} />,
              );
              layer.bindPopup(container);

              // Handle feature clicks
              layer.on({
                click: (e) => {
                  handleFeatureClick(e, featureProperties?.color ?? '#3388ff');
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
