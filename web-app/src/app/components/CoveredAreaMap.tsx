import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  ToggleButtonGroup,
  ToggleButton,
  Tooltip,
  Skeleton,
  Button,
  Typography,
  Fab,
} from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { Link } from 'react-router-dom';
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
import { type AllFeedType } from '../services/feeds/utils';
import { OpenInNew } from '@mui/icons-material';
import { computeBoundingBox } from '../screens/Feed/Feed.functions';
import { displayFormattedDate } from '../utils/date';
import { useSelector } from 'react-redux';
import ModeOfTravelIcon from '@mui/icons-material/ModeOfTravel';
import { GtfsVisualizationMap } from './GtfsVisualizationMap';
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap';
import { useRemoteConfig } from '../context/RemoteConfigProvider';
import ReactGA from 'react-ga4';
import { selectLatestGbfsVersion } from '../store/feed-selectors';
import { selectGtfsDatasetRoutesLoadingStatus } from '../store/supporting-files-selectors';

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

type MapViews =
  | 'boundingBoxView'
  | 'detailedCoveredAreaView'
  | 'gtfsVisualizationView';

const CoveredAreaMap: React.FC<CoveredAreaMapProps> = ({
  boundingBox,
  latestDataset,
  feed,
}) => {
  const { t } = useTranslation('feeds');
  const theme = useTheme();
  const { config } = useRemoteConfig();

  const [geoJsonData, setGeoJsonData] = useState<
    GeoJSONData | GeoJSONDataGBFS | null
  >(null);
  const [geoJsonError, setGeoJsonError] = useState(false);
  const [geoJsonLoading, setGeoJsonLoading] = useState(false);
  const [view, setView] = useState<MapViews>(
    feed?.data_type === 'gtfs'
      ? 'gtfsVisualizationView'
      : 'detailedCoveredAreaView',
  );

  const latestGbfsVersion = useSelector(selectLatestGbfsVersion);
  const routesJsonLoadingStatus = useSelector(
    selectGtfsDatasetRoutesLoadingStatus,
  );

  const getAndSetGeoJsonData = (urlToExtract: string): void => {
    setGeoJsonLoading(true);
    fetchGeoJson(urlToExtract)
      .then((data) => {
        setGeoJsonData(data);
        setGeoJsonError(false);
      })
      .catch(() => {
        setGeoJsonError(true);
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
  }, [latestDataset, feed]);

  // effect to determine which view to display
  useEffect(() => {
    if (feed == undefined) return;
    if (feed?.data_type === 'gbfs') return; // use default for gbfs

    // for gtfs feeds
    if (
      config.enableGtfsVisualizationMap &&
      routesJsonLoadingStatus != 'failed' &&
      boundingBox != undefined
    ) {
      setView('gtfsVisualizationView');
      return;
    }
    if (geoJsonData != null && boundingBox != undefined) {
      setView('detailedCoveredAreaView');
      return;
    }
    setView('boundingBoxView');
  }, [feed, routesJsonLoadingStatus, boundingBox, geoJsonData]);

  const handleViewChange = (
    _: React.MouseEvent<HTMLElement>,
    newView: MapViews | null,
  ): void => {
    if (newView !== null) setView(newView);
  };

  const handleOpenDetailedMapClick = (): void => {
    ReactGA.event({
      category: 'engagement',
      action: 'gtfs_visualization_open_detailed_map',
      label: 'Open Detailed Map',
    });
  };

  const getGbfsLatestVersionVisualizationUrl = (): string | undefined => {
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

    const displayGtfsVisualizationView =
      view === 'gtfsVisualizationView' && feed?.data_type === 'gtfs';

    let gbfsBoundingBox: LatLngExpression[] = [];
    if (feed?.data_type === 'gbfs') {
      if (geoJsonData == null) {
        return <></>;
      }
      gbfsBoundingBox = computeBoundingBox(geoJsonData) ?? [];
      if (gbfsBoundingBox.length === 0) {
        setGeoJsonError(true);
      }
    }

    if (displayBoundingBoxMap) {
      return <Map polygon={boundingBox ?? []} />;
    }

    if (displayGtfsVisualizationView) {
      return (
        <>
          <Fab
            size='small'
            sx={{ position: 'absolute', top: 16, right: 16 }}
            component={Link}
            to='./map'
          >
            <ZoomOutMapIcon></ZoomOutMapIcon>
          </Fab>
          <GtfsVisualizationMap
            polygon={boundingBox ?? []}
            latestDataset={latestDataset}
            dataDisplayLimit={config.visualizationMapPreviewDataLimit}
            preview={true}
            filteredRoutes={[]} // this is necessary to re-renders
            filteredRouteTypeIds={[]}
          />
        </>
      );
    }
    if (geoJsonData != null) {
      return (
        <MapGeoJSON
          geoJSONData={geoJsonData}
          polygon={boundingBox ?? gbfsBoundingBox}
          displayMapDetails={feed?.data_type === 'gtfs'}
        />
      );
    }
    return <></>;
  };

  const latestAutodiscoveryUrl = getGbfsLatestVersionVisualizationUrl();
  const enableGtfsVisualizationView = useMemo(() => {
    return (
      config.enableGtfsVisualizationMap &&
      feed?.data_type === 'gtfs' &&
      routesJsonLoadingStatus != 'failed' &&
      boundingBox != undefined
    );
  }, [
    feed?.data_type,
    config.enableGtfsVisualizationMap,
    routesJsonLoadingStatus,
    boundingBox,
  ]);

  return (
    <ContentBox
      sx={{
        flexGrow: 1,
        display: 'flex',
        flexDirection: 'column',
        maxHeight: {
          xs: '100%',
          md: '70vh', // TODO: optimize this
        },
        minHeight: '50vh',
      }}
      title={t('coveredAreaTitle') + ' - ' + t(view)}
      width={{ xs: '100%' }}
      outlineColor={theme.palette.primary.dark}
      padding={2}
    >
      <Box
        display={'flex'}
        justifyContent={
          view === 'gtfsVisualizationView' ? 'space-between' : 'flex-end'
        }
        mb={1}
        alignItems={'center'}
      >
        {view === 'gtfsVisualizationView' &&
          config.enableGtfsVisualizationMap && (
            <Button
              variant='contained'
              disableElevation
              component={Link}
              to='./map'
              onClick={handleOpenDetailedMapClick}
              endIcon={<OpenInNewIcon></OpenInNewIcon>}
            >
              {t('openDetailedMap')}
            </Button>
          )}
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
            {config.enableGtfsVisualizationMap && (
              <Tooltip title={t('gtfsVisualizationTooltip')}>
                <ToggleButton
                  value='gtfsVisualizationView'
                  disabled={!enableGtfsVisualizationView}
                  aria-label={t('gtfsVisualizationViewLabel')}
                >
                  <ModeOfTravelIcon />
                </ToggleButton>
              </Tooltip>
            )}
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
      </Box>
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
          {geoJsonLoading || routesJsonLoadingStatus === 'loading' ? (
            <Skeleton
              variant='rectangular'
              width='100%'
              height='100%'
              animation='wave'
            />
          ) : (
            <>{renderMap()}</>
          )}
        </Box>
      )}
    </ContentBox>
  );
};

export default CoveredAreaMap;
