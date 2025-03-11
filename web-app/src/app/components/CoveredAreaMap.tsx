import React, { useState } from 'react';
import { Box, ToggleButtonGroup, ToggleButton, Tooltip } from '@mui/material';
import MapIcon from '@mui/icons-material/Map';
import TravelExploreIcon from '@mui/icons-material/TravelExplore';
import { ContentBox } from './ContentBox';
import { WarningContentBox } from './WarningContentBox';
import { mapBoxPositionStyle } from '../screens/Feed/Feed.styles';
import { type GeoJSONData, MapGeoJSON } from './MapGeoJSON';
import { Map } from './Map';
import { useTranslation } from 'react-i18next';
import type { LatLngExpression } from 'leaflet';
import { useTheme } from '@mui/material/styles';
interface CoveredAreaMapProps {
  boundingBox?: LatLngExpression[]; // Replace 'any' with your actual type
  latestDataset?: { hosted_url?: string };
}

export const fetchGeoJson = async (
  latestDatasetUrl: string,
): Promise<GeoJSONData> => {
  const geoJsonUrl = latestDatasetUrl
    .split('/')
    .slice(0, -2)
    .concat('geolocation.geojson')
    .join('/');
  const response = await fetch(geoJsonUrl);
  if (!response.ok) {
    throw new Error('Failed to fetch GeoJSON');
  }
  return await response.json();
};

const CoveredAreaMap: React.FC<CoveredAreaMapProps> = ({
  boundingBox,
  latestDataset,
}) => {
  const { t } = useTranslation('feeds');
  const theme = useTheme();
  const [geoJsonError, setGeoJsonError] = React.useState(false);
  const [geoJsonData, setGeoJsonData] = React.useState<GeoJSONData | null>(
    null,
  );
  React.useEffect(() => {
    if (latestDataset?.hosted_url != undefined) {
      fetchGeoJson(latestDataset.hosted_url).then(
        (data) => {
          setGeoJsonData(data);
        },
        (_) => {
          setGeoJsonError(true);
        },
      );
    }
  }, [latestDataset]);

  const [view, setView] = useState<
    'boundingBoxView' | 'detailedCoveredAreaView'
  >('detailedCoveredAreaView');

  const handleViewChange = (
    _: React.MouseEvent<HTMLElement>,
    newView: 'boundingBoxView' | 'detailedCoveredAreaView' | null,
  ): void => {
    // Only update state if a non-null value is returned
    if (newView !== null) {
      setView(newView);
    }
  };

  return (
    <ContentBox
      sx={{
        flexGrow: 1,
        display: 'flex',
        flexDirection: 'column',
      }}
      title={t('coveredAreaTitle') + ' - ' + t(view)}
      width={{ xs: '100%' }}
      outlineColor={theme.palette.primary.dark}
      padding={2}
      action={
        <ToggleButtonGroup
          value={view}
          color='primary'
          exclusive
          aria-label='map view selection'
          onChange={handleViewChange}
        >
          <Tooltip title={t('detailedCoveredAreaViewTooltip')}>
            <ToggleButton
              value='detailedCoveredAreaView'
              disabled={geoJsonError || boundingBox === undefined}
              aria-label='Detailed Covered Area View'
            >
              <TravelExploreIcon />
            </ToggleButton>
          </Tooltip>
          <Tooltip title={t('boundingBoxViewTooltip')}>
            <ToggleButton
              value='boundingBoxView'
              aria-label='Bounding Box View'
            >
              <MapIcon />
            </ToggleButton>
          </Tooltip>
        </ToggleButtonGroup>
      }
    >
      {boundingBox === undefined && view === 'boundingBoxView' && (
        <WarningContentBox>
          {t('unableToGenerateBoundingBox')}
        </WarningContentBox>
      )}

      {boundingBox !== undefined && (
        <Box sx={mapBoxPositionStyle}>
          {view === 'boundingBoxView' ? (
            <Map polygon={boundingBox} />
          ) : (
            <MapGeoJSON geoJSONData={geoJsonData} polygon={boundingBox} />
          )}
        </Box>
      )}
    </ContentBox>
  );
};

export default CoveredAreaMap;
