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
import { selectLatestGbfsVersion } from '../store/feed-selectors';
import ModeOfTravelIcon from '@mui/icons-material/ModeOfTravel';
import { GtfsVisualizationMap } from './GtfsVisualizationMap';
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap';
import { useRemoteConfig } from '../context/RemoteConfigProvider';
import ReactGA from 'react-ga4';
import { selectGtfsDatasetRoutesJson } from '../store/supporting-files-selectors';

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
  const routes = useSelector(selectGtfsDatasetRoutesJson);
  const [preferVizUntil, setPreferVizUntil] = useState<number>(0);

  useEffect(() => {
    if (feed?.data_type === 'gtfs' && config.enableGtfsVisualizationMap) {
      // start a short grace window whenever the feed changes (or page refreshes)
      setPreferVizUntil(Date.now() + 2000); // ~1.2s
      // update value in 2s
      setTimeout(() => {
        setPreferVizUntil(0);
      }, 2000);
    }
  }, [
    feed?.data_type,
    config.enableGtfsVisualizationMap,
    latestDataset?.hosted_url,
  ]);

  const waitingForVizDecision = useMemo(() => {
    const maybeViz =
      feed?.data_type === 'gtfs' && config.enableGtfsVisualizationMap;
    const noRoutesYet = routes === undefined || routes.length <= 1; // <=1 means not eligible *yet*
    const withinGrace = Date.now() < preferVizUntil;
    console.log('withinGrace', withinGrace);
    return maybeViz && noRoutesYet && withinGrace;
  }, [
    feed?.data_type,
    config.enableGtfsVisualizationMap,
    routes,
    preferVizUntil,
  ]);

  const getDataAndSetView = (urlToExtract: string): void => {
    console.log('getDataAndSetView called with', urlToExtract);
    if (
      feed?.data_type === 'gtfs' &&
      routes !== undefined &&
      routes.length > 1
    ) {
      setView('gtfsVisualizationView');
      if (geoJsonData !== null) {
        // we already have geojson; keep it for overlay/future toggle
        // but don't switch away from viz
        return;
      }
    } else if (feed?.data_type === 'gtfs') {
      setView('boundingBoxView');
    }

    setGeoJsonLoading(true);
    fetchGeoJson(urlToExtract)
      .then((data) => {
        console.log('getDataAndSetView', data);
        setGeoJsonData(data);
        setGeoJsonError(false);

        const vizDefinitelyNotHappening =
          feed?.data_type !== 'gtfs' ||
          !config.enableGtfsVisualizationMap ||
          // don't give up until grace passes and routes have finished resolving (but still not eligible)
          (Date.now() >= preferVizUntil &&
            (routes === undefined || routes.length <= 1));
        console.log('vizDefinitelyNotHappening', vizDefinitelyNotHappening);
        if (vizDefinitelyNotHappening) {
          console.log('its set here -- if statement 1');
          setView('detailedCoveredAreaView');
        }
      })
      .catch(() => {
        console.log('error fetching geojson');
        setGeoJsonError(true);
      })
      .finally(() => {
        console.log('geojson fetch attempt finished and set to false');
        setGeoJsonLoading(false);
      });
  };

  useEffect(() => {
    if (feed?.data_type === 'gbfs') {
      console.log('are we in here?');
      console.log(latestGbfsVersion);
      const latestGbfsVersionReportUrl =
        latestGbfsVersion?.latest_validation_report?.report_summary_url;
      console.log('latestGbfsVersionReportUrl', latestGbfsVersionReportUrl);
      if (latestGbfsVersionReportUrl === undefined) {
        setGeoJsonData(null);
        setGeoJsonError(true);
        return;
      }
      getDataAndSetView(latestGbfsVersionReportUrl);
      return;
    }
    if (
      feed?.data_type === 'gtfs' &&
      latestDataset?.hosted_url != undefined &&
      boundingBox != undefined
    ) {
      getDataAndSetView(latestDataset.hosted_url);
      return;
    }
    setGeoJsonData(null);
    setGeoJsonError(true);
    setView('boundingBoxView');
  }, [latestDataset, feed, routes, latestGbfsVersion, preferVizUntil]);

  const handleViewChange = (
    _: React.MouseEvent<HTMLElement>,
    newView: MapViews | null,
  ): void => {
    console.log('its set here -- on click');
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

  const enableGtfsVisualizationView = useMemo(() => {
    console.log('enableGtfsVisualizationView');
    console.log('the routes are', routes);
    return (
      feed?.data_type === 'gtfs' &&
      config.enableGtfsVisualizationMap &&
      routes !== undefined &&
      boundingBox != undefined &&
      routes.length > 1 &&
      Date.now() >= preferVizUntil
    );
  }, [
    feed?.data_type,
    config.enableGtfsVisualizationMap,
    routes,
    boundingBox,
    preferVizUntil,
  ]);

  const renderMap = (): JSX.Element => {
    // if we're GTFS and still deciding about viz, show skeleton instead of falling back early
    if (waitingForVizDecision) {
      console.log('waitingForVizDecision');
      return (
        <Skeleton
          variant='rectangular'
          width='100%'
          height='100%'
          animation='wave'
        />
      );
    }
    console.log('the bouding box is', boundingBox);
    console.log('the view is', view);

    const displayBoundingBoxMap =
      view === 'boundingBoxView' && feed?.data_type === 'gtfs';

    const displayGtfsVisualizationView =
      view === 'gtfsVisualizationView' && feed?.data_type === 'gtfs';

    let gbfsBoundingBox: LatLngExpression[] = [];
    if (feed?.data_type === 'gbfs') {
      if (geoJsonData == null) {
        return <></>;
      }
      console.log('geojson data for gbfs is', geoJsonData);
      gbfsBoundingBox = computeBoundingBox(geoJsonData) ?? [];
      console.log('GBFS bounding box computed as', gbfsBoundingBox);
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
            <ZoomOutMapIcon />
          </Fab>
          <GtfsVisualizationMap
            polygon={boundingBox ?? []}
            latestDataset={latestDataset}
          />
        </>
      );
    }

    return (
      <MapGeoJSON
        geoJSONData={geoJsonData}
        polygon={boundingBox ?? gbfsBoundingBox}
        displayMapDetails={feed?.data_type === 'gtfs'}
      />
    );
  };

  const latestAutodiscoveryUrl = getGbfsLatestVersionVisualizationUrl();
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
                  disabled={
                    !config.enableGtfsVisualizationMap ||
                    !enableGtfsVisualizationView
                  }
                  aria-label='Bounding Box View'
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

      {/* {(feed?.data_type === 'gtfs' || boundingBox != undefined) && ( */}
      {/*  <Box sx={mapBoxPositionStyle}> */}
      {/*    {geoJsonLoading && !enableGtfsVisualizationView ? ( */}
      {/*      <Skeleton */}
      {/*        variant='rectangular' */}
      {/*        width='100%' */}
      {/*        height='100%' */}
      {/*        animation='wave' */}
      {/*      /> */}
      {/*    ) : ( */}
      {/*      <>{renderMap()}</> */}
      {/*    )} */}
      {/*  </Box> */}
      {/* )} */}

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
            <>{renderMap()}</>
          )}
        </Box>
      )}
    </ContentBox>
  );
};

export default CoveredAreaMap;
