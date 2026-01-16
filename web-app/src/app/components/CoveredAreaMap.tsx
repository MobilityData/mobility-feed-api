'use client';

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
import Link from 'next/link';
import MapIcon from '@mui/icons-material/Map';
import TravelExploreIcon from '@mui/icons-material/TravelExplore';
import { WarningContentBox } from './WarningContentBox';
import { mapBoxPositionStyle } from '../screens/Feed/Feed.styles';
import dynamic from 'next/dynamic';
import { type GeoJSONData, type GeoJSONDataGBFS } from './MapGeoJSON';
import { useTranslations } from 'next-intl';
import type { LatLngExpression, LatLngTuple } from 'leaflet';
import { useTheme } from '@mui/material/styles';
import {
  type GTFSFeedType,
  type AllFeedType,
  type GBFSFeedType,
  type GBFSVersionType,
} from '../services/feeds/utils';
import { OpenInNew } from '@mui/icons-material';
import { computeBoundingBox } from '../screens/Feed/Feed.functions';
import { displayFormattedDate } from '../utils/date';
import { useSelector } from 'react-redux';
import ModeOfTravelIcon from '@mui/icons-material/ModeOfTravel';
import { GtfsVisualizationMap } from './GtfsVisualizationMap';
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap';
import { useRemoteConfig } from '../context/RemoteConfigProvider';
import ReactGA from 'react-ga4';
import { selectGtfsDatasetRoutesLoadingStatus } from '../store/supporting-files-selectors';
import {
  getLatestGbfsVersion,
  type LatestDatasetLite,
} from './GtfsVisualizationMap.functions';

// Dynamically import Map and MapGeoJSON for code splitting and bundle size
// Useful since these components are rendered conditionally to the tab and will only import when on page
const MapGeoJSON = dynamic(
  async () => await import('./MapGeoJSON').then((mod) => mod.MapGeoJSON),
  { ssr: false },
);
const Map = dynamic(async () => await import('./Map').then((mod) => mod.Map), {
  ssr: false,
});

interface CoveredAreaMapProps {
  boundingBox?: LatLngTuple[];
  latestDataset?: LatestDatasetLite;
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
  const t = useTranslations('feeds');
  const tCommon = useTranslations('common');
  const theme = useTheme();
  const { config } = useRemoteConfig();

  const [geoJsonData, setGeoJsonData] = useState<
    GeoJSONData | GeoJSONDataGBFS | null
  >(null);
  const [geoJsonError, setGeoJsonError] = useState(false);
  const [geoJsonLoading, setGeoJsonLoading] = useState(false);
  const [view, setView] = useState<MapViews>(
    feed?.data_type === 'gtfs' ? 'gtfsVisualizationView' : 'boundingBoxView',
  );

  const latestGbfsVersion = useMemo((): GBFSVersionType | undefined => {
    if (feed?.data_type !== 'gbfs') return undefined;
    return getLatestGbfsVersion(feed as GBFSFeedType);
  }, [feed]);

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
      if (
        !config.enableDetailedCoveredArea ||
        latestGbfsVersionReportUrl === undefined
      ) {
        setGeoJsonData(null);
        setGeoJsonError(config.enableDetailedCoveredArea);
        return;
      }
      getAndSetGeoJsonData(latestGbfsVersionReportUrl);
      return;
    }
    if (
      feed?.data_type === 'gtfs' &&
      latestDataset?.hosted_url != undefined &&
      boundingBox != undefined &&
      config.enableDetailedCoveredArea
    ) {
      getAndSetGeoJsonData(latestDataset.hosted_url);
      return;
    }
    setGeoJsonData(null);
    setGeoJsonError(config.enableDetailedCoveredArea);
  }, [latestDataset, feed, config.enableDetailedCoveredArea]);

  // effect to determine which view to display
  useEffect(() => {
    if (feed == undefined) return;
    if (feed?.data_type === 'gbfs') {
      setView(
        config.enableDetailedCoveredArea
          ? 'detailedCoveredAreaView'
          : 'boundingBoxView',
      );
      return;
    }

    // for gtfs feeds
    if (
      feed?.data_type === 'gtfs' &&
      config.enableGtfsVisualizationMap &&
      routesJsonLoadingStatus != 'failed' &&
      boundingBox != undefined
    ) {
      setView('gtfsVisualizationView');
      return;
    }
    if (
      config.enableDetailedCoveredArea &&
      geoJsonData != null &&
      boundingBox != undefined
    ) {
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
      view === 'boundingBoxView' &&
      (feed?.data_type === 'gtfs' ||
        (feed?.data_type === 'gbfs' && boundingBox != null));

    const displayGtfsVisualizationView =
      view === 'gtfsVisualizationView' && feed?.data_type === 'gtfs';

    if (displayBoundingBoxMap && boundingBox != undefined) {
      return <Map key={`bbox-${feed?.id}`} polygon={boundingBox} />;
    }

    if (
      displayGtfsVisualizationView &&
      boundingBox != undefined &&
      feed.data_type === 'gtfs'
    ) {
      const gtfsFeed = feed as GTFSFeedType;
      return (
        <>
          <Fab
            size='small'
            sx={{ position: 'absolute', top: 16, right: 16 }}
            component={Link}
            href='./map'
          >
            <ZoomOutMapIcon></ZoomOutMapIcon>
          </Fab>
          <GtfsVisualizationMap
            polygon={boundingBox}
            latestDataset={latestDataset}
            visualizationId={
              gtfsFeed?.visualization_dataset_id ?? latestDataset?.id ?? ''
            }
            dataDisplayLimit={config.visualizationMapPreviewDataLimit}
            preview={true}
            filteredRoutes={[]} // this is necessary to re-renders
            filteredRouteTypeIds={[]}
          />
        </>
      );
    }
    if (config.enableDetailedCoveredArea && geoJsonData != null) {
      let gbfsGeoJsonBoundingBox: LatLngTuple[] = [];
      if (feed?.data_type === 'gbfs') {
        gbfsGeoJsonBoundingBox = computeBoundingBox(geoJsonData) ?? [];
        if (gbfsGeoJsonBoundingBox.length === 0) {
          setGeoJsonError(true);
        }
      }
      const feedBoundingBox: LatLngExpression[] =
        feed?.data_type === 'gtfs' ? boundingBox ?? [] : gbfsGeoJsonBoundingBox;
      return (
        <MapGeoJSON
          key={`geojson-${feed?.id}`}
          geoJSONData={geoJsonData}
          polygon={feedBoundingBox}
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
    <Box
      sx={{
        position: 'sticky',
        top: '74px',
        flexGrow: 1,
        display: 'flex',
        flexDirection: 'column',
        maxHeight: '90vh',
        minHeight: '50vh',
        p: 2,
        backgroundColor: theme.palette.background.default,
        borderRadius: '5px',
        border: 'none',
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Typography
          variant='subtitle1'
          sx={{ color: 'text.secondary', mt: 0.5 }}
        >
          {t('coveredAreaTitle') + ' - ' + t(view)}
        </Typography>
        {feed?.data_type === 'gbfs' && (
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
                {tCommon('updated')}:{' '}
                {displayFormattedDate(
                  (geoJsonData as GeoJSONDataGBFS).extracted_at,
                )}
              </Typography>
            )}
          </Box>
        )}
        {feed?.data_type === 'gtfs' && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
            {view === 'gtfsVisualizationView' &&
              config.enableGtfsVisualizationMap && (
                <Button
                  variant='text'
                  disableElevation
                  component={Link}
                  href='./map'
                  onClick={handleOpenDetailedMapClick}
                  endIcon={<OpenInNewIcon></OpenInNewIcon>}
                >
                  {t('openDetailedMap')}
                </Button>
              )}
            <ToggleButtonGroup
              value={view}
              color='primary'
              exclusive
              aria-label='map view selection'
              onChange={handleViewChange}
              size='small'
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
              {config.enableDetailedCoveredArea && (
                <Tooltip title={t('detailedCoveredAreaViewTooltip')}>
                  <ToggleButton
                    value='detailedCoveredAreaView'
                    disabled={
                      geoJsonLoading ||
                      geoJsonError ||
                      boundingBox === undefined
                    }
                    aria-label='Detailed Covered Area View'
                  >
                    <TravelExploreIcon />
                  </ToggleButton>
                </Tooltip>
              )}
              <Tooltip title={t('boundingBoxViewTooltip')}>
                <ToggleButton
                  value='boundingBoxView'
                  aria-label='Bounding Box View'
                >
                  <MapIcon />
                </ToggleButton>
              </Tooltip>
            </ToggleButtonGroup>
          </Box>
        )}
      </Box>
      {(feed?.data_type === 'gtfs' || feed?.data_type === 'gbfs') &&
        boundingBox === undefined &&
        view === 'boundingBoxView' && (
          <WarningContentBox>
            {t('unableToGenerateBoundingBox')}
          </WarningContentBox>
        )}

      {config.enableDetailedCoveredArea &&
        feed?.data_type === 'gbfs' &&
        geoJsonError && (
          <WarningContentBox>{t('unableToGetGbfsMap')}</WarningContentBox>
        )}

      {(boundingBox != undefined || !geoJsonError) && (
        <Box key={view} sx={mapBoxPositionStyle}>
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
    </Box>
  );
};

export default CoveredAreaMap;
