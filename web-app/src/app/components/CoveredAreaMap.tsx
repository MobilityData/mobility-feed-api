import React, { useState, useEffect } from 'react';
import {
  Box,
  ToggleButtonGroup,
  ToggleButton,
  Tooltip,
  Skeleton,
  Button,
  Typography,
} from '@mui/material';
import MapIcon from '@mui/icons-material/Map';
import TravelExploreIcon from '@mui/icons-material/TravelExplore';
import { ContentBox } from './ContentBox';
import { WarningContentBox } from './WarningContentBox';
import { mapBoxPositionStyle } from '../screens/Feed/Feed.styles';
import {
  type GeoJSONData,
  type GeoJSONDataGBFS,
  MapGeoJSON,
} from './MapGeoJSON';
import { Map } from './Map';
import { useTranslation } from 'react-i18next';
import type { LatLngExpression } from 'leaflet';
import { useTheme } from '@mui/material/styles';
import { type GBFSFeedType, type AllFeedType } from '../services/feeds/utils';
import { OpenInNew } from '@mui/icons-material';
import { computeBoundingBox } from '../screens/Feed/Feed.functions';
import { displayFormattedDate } from '../utils/date';
import { useSelector } from 'react-redux';
import { selectAutodiscoveryGbfsVersion } from '../store/feed-selectors';

interface CoveredAreaMapProps {
  boundingBox?: LatLngExpression[];
  latestDataset?: { hosted_url?: string };
  feed: AllFeedType;
}

export const fetchGeoJson = async (
  latestDatasetUrl: string,
): Promise<GeoJSONData | GeoJSONDataGBFS> => {
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
  feed,
}) => {
  const { t } = useTranslation('feeds');
  const theme = useTheme();

  const [geoJsonData, setGeoJsonData] = useState<
    GeoJSONData | GeoJSONDataGBFS | null
  >(null);
  const [geoJsonError, setGeoJsonError] = useState(false);
  const [geoJsonLoading, setGeoJsonLoading] = useState(false);
  const [view, setView] = useState<
    'boundingBoxView' | 'detailedCoveredAreaView'
  >('detailedCoveredAreaView');
  const latestGbfsVersion = useSelector(selectAutodiscoveryGbfsVersion);

  const getAndSetGeoJsonData = (urlToExtract: string): void => {
    setGeoJsonLoading(true);
    fetchGeoJson(urlToExtract)
      .then((data) => {
        setGeoJsonData(data);
        setGeoJsonError(false);
        setView('detailedCoveredAreaView');
      })
      .catch(() => {
        setGeoJsonError(true);
        setView('boundingBoxView');
      })
      .finally(() => {
        setGeoJsonLoading(false);
      });
  };

  useEffect(() => {
    if (feed?.data_type === 'gbfs') {
      const latestGbfsVersionReportUrl =
        latestGbfsVersion?.latest_validation_report?.report_summary_url;
      if (latestGbfsVersionReportUrl === undefined) {
        setGeoJsonData(null);
        setGeoJsonError(true);
        return;
      }
      getAndSetGeoJsonData(latestGbfsVersionReportUrl);
      return;
    }
    if (
      feed?.data_type === 'gtfs' &&
      latestDataset?.hosted_url != undefined &&
      boundingBox != undefined
    ) {
      getAndSetGeoJsonData(latestDataset.hosted_url);
      return;
    }
    setGeoJsonData(null);
    setGeoJsonError(true);
    setView('boundingBoxView');
  }, [latestDataset, feed]);

  const handleViewChange = (
    _: React.MouseEvent<HTMLElement>,
    newView: 'boundingBoxView' | 'detailedCoveredAreaView' | null,
  ): void => {
    if (newView !== null) setView(newView);
  };

  const getGbfsLatestVersionVisualizationUrl = (
    feed: GBFSFeedType,
  ): string | undefined => {
    const latestAutodiscoveryUrl = latestGbfsVersion?.endpoints?.find(
      (endpoint) => endpoint.name === 'gbfs',
    )?.url;
    if (latestAutodiscoveryUrl != undefined) {
      return `https://gbfs-validator.mobilitydata.org/visualization?url=${latestAutodiscoveryUrl}`;
    }
    return undefined;
  };

  const renderMap = (): JSX.Element => {
    const displayBoundingBoxMap =
      view === 'boundingBoxView' && feed?.data_type === 'gtfs';
    let gbfsBoundingBox: LatLngExpression[] = [];
    if (feed?.data_type === 'gbfs') {
      gbfsBoundingBox = computeBoundingBox(geoJsonData) ?? [];
      if (gbfsBoundingBox.length === 0) {
        setGeoJsonError(true);
      }
    }
    return (
      <>
        {displayBoundingBoxMap ? (
          <Map polygon={boundingBox ?? []} />
        ) : (
          <MapGeoJSON
            geoJSONData={geoJsonData}
            polygon={boundingBox ?? gbfsBoundingBox}
            displayMapDetails={feed?.data_type === 'gtfs'}
          />
        )}
      </>
    );
  };

  const mapDisplayError = boundingBox == undefined && geoJsonError;
  const latestAutodiscoveryUrl = getGbfsLatestVersionVisualizationUrl(
    feed as GBFSFeedType,
  );
  return (
    <ContentBox
      sx={{
        flexGrow: 1,
        display: 'flex',
        flexDirection: 'column',
        maxHeight: {
          xs: '100%',
          md: '70vh',
        },
        minHeight: '50vh',
      }}
      title={mapDisplayError ? '' : t('coveredAreaTitle') + ' - ' + t(view)}
      width={{ xs: '100%' }}
      outlineColor={theme.palette.primary.dark}
      padding={2}
      action={
        <>
          {feed?.data_type === 'gbfs' ? (
            <Box sx={{ textAlign: 'right' }}>
              {latestAutodiscoveryUrl != undefined && (
                <Button
                  href={latestAutodiscoveryUrl}
                  target='_blank'
                  rel='noreferrer'
                  endIcon={<OpenInNew />}
                >
                  {t('viewRealtimeVisualization')}
                </Button>
              )}
              {(geoJsonData as GeoJSONDataGBFS)?.extracted_at != undefined && (
                <Typography
                  variant='caption'
                  color='text.secondary'
                  sx={{ display: 'block', px: 1 }}
                >
                  {t('common:updated')}:{' '}
                  {displayFormattedDate(
                    (geoJsonData as GeoJSONDataGBFS).extracted_at,
                  )}
                </Typography>
              )}
            </Box>
          ) : (
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
                  disabled={
                    geoJsonLoading || geoJsonError || boundingBox === undefined
                  }
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
          )}
        </>
      }
    >
      {feed?.data_type === 'gtfs' &&
        boundingBox === undefined &&
        view === 'boundingBoxView' && (
          <WarningContentBox>
            {t('unableToGenerateBoundingBox')}
          </WarningContentBox>
        )}

      {feed?.data_type === 'gbfs' && geoJsonError && (
        <WarningContentBox>{t('unableToGetGbfsMap')}</WarningContentBox>
      )}

      {(boundingBox != undefined || !geoJsonError) && (
        <Box sx={mapBoxPositionStyle}>
          {geoJsonLoading ? (
            <Skeleton
              variant='rectangular'
              width='100%'
              height='100%'
              animation='wave'
            />
          ) : (
            <>{geoJsonData !== null && <>{renderMap()}</>}</>
          )}
        </Box>
      )}
    </ContentBox>
  );
};

export default CoveredAreaMap;
