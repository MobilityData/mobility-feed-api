import {
  Box,
  Fab,
  Button,
  Chip,
  useTheme,
  Skeleton,
  Alert,
  AlertTitle,
  Stack,
  ClickAwayListener,
  Paper,
  Typography,
  Slider,
  ToggleButtonGroup,
  ToggleButton,
} from '@mui/material';
import React, { useEffect, useMemo, useState } from 'react';
import { GtfsVisualizationMap } from '../../../components/GtfsVisualizationMap';
import CloseIcon from '@mui/icons-material/Close';
import NestedCheckboxList, {
  type CheckboxStructure,
} from '../../../components/NestedCheckboxList';
import { CenterFocusStrong, ChevronLeft } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { SearchHeader } from '../../../styles/Filters.styles';
import FilterAltIcon from '@mui/icons-material/FilterAlt';
import TuneIcon from '@mui/icons-material/Tune';
import {
  StyledChipFilterContainer,
  StyledMapControlPanel,
} from '../Map.styles';
import {
  selectFeedData,
  selectFeedLoadingStatus,
  selectGtfsDatasetRoutesJson,
  selectGtfsDatasetRoutesLoadingStatus,
  selectGtfsDatasetRouteTypes,
  selectFeedBoundingBox,
  selectIsAnonymous,
  selectIsAuthenticated,
  selectUserProfile,
} from '../../../store/selectors';
import { useSelector } from 'react-redux';
import { useParams, useNavigate } from 'react-router-dom';
import { clearDataset } from '../../../store/dataset-reducer';
import { useAppDispatch } from '../../../hooks';
import { useRemoteConfig } from '../../../context/RemoteConfigProvider';
import { getRouteTypeTranslatedName } from '../../../constants/RouteTypes';
import { loadingFeed } from '../../../store/feed-reducer';
import type { GTFSFeedType } from '../../../services/feeds/utils';
import RouteSelector from '../../../components/RouteSelector';

export default function FullMapView(): React.ReactElement {
  const { t } = useTranslation('feeds');
  const { config } = useRemoteConfig();

  const { feedId } = useParams();
  const navigate = useNavigate();

  const theme = useTheme();
  const dispatch = useAppDispatch();

  const user = useSelector(selectUserProfile);
  const feed = useSelector(selectFeedData);
  const needsToLoadFeed =
    feed === undefined || (feed?.id != null && feed?.id !== feedId);
  const feedLoadingStatus = useSelector(selectFeedLoadingStatus);
  const routesJsonLoadingStatus = useSelector(
    selectGtfsDatasetRoutesLoadingStatus,
  );

  const isAuthenticatedOrAnonymous =
    useSelector(selectIsAuthenticated) || useSelector(selectIsAnonymous);

  const gtfsFeed = useSelector(selectFeedData) as GTFSFeedType | undefined;
  const latestDatasetLite = {
    hosted_url: gtfsFeed?.latest_dataset?.hosted_url,
    id: gtfsFeed?.latest_dataset?.id,
  };
  const boundingBox = useSelector(selectFeedBoundingBox);
  const routes = useSelector(selectGtfsDatasetRoutesJson);
  const routeTypes = useSelector(selectGtfsDatasetRouteTypes);

  const [filteredRoutes, setFilteredRoutes] = useState<string[]>([]);
  const [filteredRouteTypeIds, setFilteredRouteTypeIds] = useState<string[]>(
    [],
  );
  const [refocusTrigger, setRefocusTrigger] = useState<boolean>(false);
  const [hideStops, setHideStops] = useState<boolean>(false);
  const [showMapControlMobile, setShowMapControlMobile] =
    useState<boolean>(false);

  /* style panel state */
  const [stylePanelOpen, setStylePanelOpen] = useState<boolean>(false);
  // Presets: small=3, medium=5, large=7 (works nicely with your current map defaults)
  const [stopPreset, setStopPreset] = useState<
    'small' | 'medium' | 'large' | 'custom'
  >('small');
  const [customStopRadius, setCustomStopRadius] = useState<number>(3);

  const currentStopRadius =
    stopPreset === 'small'
      ? 3
      : stopPreset === 'medium'
        ? 5
        : stopPreset === 'large'
          ? 7
          : customStopRadius; // 'custom'

  // kick off feed loading when user or feedId changes and we need to load the feed
  useEffect(() => {
    if (isAuthenticatedOrAnonymous && feedId != null && needsToLoadFeed) {
      dispatch(clearDataset());
      dispatch(loadingFeed({ feedId }));
    }
  }, [dispatch, isAuthenticatedOrAnonymous, user, feedId, needsToLoadFeed]);

  const clearAllFilters = (): void => {
    setFilteredRoutes([]);
    setFilteredRouteTypeIds([]);
    setHideStops(false);
  };

  const getRouteDisplayName = (routeId: string): string => {
    const route = (routes ?? []).find((r) => r.routeId === routeId);
    return route != null ? `${route.routeId} - ${route.routeName}` : routeId;
  };

  const getRouteType = (routeId: string): string | undefined => {
    const route = (routes ?? []).find((r) => r.routeId === routeId);
    return route?.routeType;
  };

  const getUniqueRouteTypesCheckboxData = (): CheckboxStructure[] =>
    (routeTypes ?? []).map((routeTypeId) => {
      const translatedName = getRouteTypeTranslatedName(routeTypeId, t);
      return {
        title: translatedName,
        checked: filteredRouteTypeIds.includes(routeTypeId),
        props: { routeTypeId },
        type: 'checkbox',
      };
    }) as CheckboxStructure[];

  const isFetchingFeed = needsToLoadFeed || feedLoadingStatus === 'loading';

  const isFetchingRoutes = routesJsonLoadingStatus === 'loading';

  const isGtfsFeed = (feed as GTFSFeedType)?.data_type === 'gtfs';
  const feedError = feedLoadingStatus === 'error';
  const routesError = routesJsonLoadingStatus === 'failed';
  const hasLoadingError = feedError || routesError;
  const isLoading = !hasLoadingError && (isFetchingFeed || isFetchingRoutes);
  const missingBboxAfterLoad =
    boundingBox == null &&
    !isLoading &&
    feedLoadingStatus === 'loaded' &&
    routesJsonLoadingStatus === 'loaded';

  const hasError =
    feedError ||
    routesError ||
    (!isGtfsFeed && feed == null) ||
    missingBboxAfterLoad;

  const errorDetails = useMemo(() => {
    const messages: string[] = [];
    if (feedError) messages.push(t('visualizationMapErrors.noFeedMetadata'));
    if (routesError) messages.push(t('visualizationMapErrors.noRoutesData'));
    if (feed != null && !isGtfsFeed)
      messages.push(t('visualizationMapErrors.invalidDataType'));
    if (missingBboxAfterLoad)
      messages.push(t('visualizationMapErrors.noBoundingBox'));
    return messages;
  }, [feedError, routesError, isGtfsFeed, feed, missingBboxAfterLoad, t]);

  const renderFilterChips = (): React.ReactElement => (
    <StyledChipFilterContainer id='map-filters'>
      {(filteredRoutes.length > 0 ||
        filteredRouteTypeIds.length > 0 ||
        hideStops) && (
        <Button
          variant='text'
          onClick={clearAllFilters}
          size='small'
          color='primary'
        >
          {t('fullMapView.clearAll')}
        </Button>
      )}
      {hideStops && (
        <Chip
          color='primary'
          variant='outlined'
          size='small'
          label={t('fullMapView.hideStops')}
          onDelete={() => {
            setHideStops(false);
          }}
          sx={{ cursor: 'pointer' }}
        />
      )}
      {filteredRouteTypeIds.map((routeTypeId) => (
        <Chip
          color='primary'
          variant='outlined'
          size='small'
          key={routeTypeId}
          label={getRouteTypeTranslatedName(routeTypeId, t)}
          onDelete={() => {
            setFilteredRouteTypeIds((prev) =>
              prev.filter((type) => type !== routeTypeId),
            );
            // Also drop route IDs that are no longer valid
            setFilteredRoutes((prev) =>
              prev.filter((rid) => getRouteType(rid) !== routeTypeId),
            );
          }}
          sx={{ cursor: 'pointer' }}
        />
      ))}
      {filteredRoutes.map((routeId) => (
        <Chip
          color='primary'
          variant='outlined'
          size='small'
          key={routeId}
          label={getRouteDisplayName(routeId)}
          onDelete={() => {
            setFilteredRoutes((prev) => prev.filter((id) => id !== routeId));
          }}
          sx={{ cursor: 'pointer' }}
        />
      ))}
    </StyledChipFilterContainer>
  );

  const renderPanelSkeleton = (): React.ReactElement => (
    <Box sx={{ p: { xs: 1, md: 0 } }}>
      <Skeleton variant='text' width='60%' height={28} sx={{ mb: 1 }} />
      {[...Array(5)].map((_, i) => (
        <Skeleton
          key={i}
          variant='rectangular'
          height={28}
          sx={{ mb: 1, borderRadius: 1 }}
        />
      ))}
      <Skeleton variant='text' width='40%' height={28} sx={{ mt: 2, mb: 1 }} />
      <Skeleton
        variant='rectangular'
        height={28}
        sx={{ mb: 1, borderRadius: 1 }}
      />
      <Skeleton variant='text' width='50%' height={28} sx={{ mt: 2, mb: 1 }} />
      {[...Array(3)].map((_, i) => (
        <Skeleton
          key={`r-${i}`}
          variant='rectangular'
          height={36}
          sx={{ mb: 1, borderRadius: 1 }}
        />
      ))}
    </Box>
  );

  const renderMapSkeleton = (): React.ReactElement => (
    <Skeleton variant='rectangular' width='100%' height='100%' />
  );

  const renderError = (): React.ReactElement => (
    <Box
      sx={{
        p: 2,
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: theme.palette.background.default,
      }}
    >
      <Stack spacing={2} sx={{ maxWidth: 720 }}>
        <Alert severity='error' variant='filled'>
          <AlertTitle>
            {t('visualizationMapErrors.errorDescription')}
          </AlertTitle>
          <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 18 }}>
            {errorDetails.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </Alert>
      </Stack>
    </Box>
  );

  if (!config.enableGtfsVisualizationMap) {
    return (
      <Box>
        <Alert severity='error' sx={{ m: 2 }}>
          <AlertTitle>{t('fullMapView.disabledTitle')}</AlertTitle>
          {t('fullMapView.disabledDescription')}
        </Alert>
      </Box>
    );
  }

  return (
    <>
      <Box
        sx={{
          width: '100%',
          position: 'relative',
          display: 'flex',
          pt: 1,
          height: 'calc(100vh - 64px - 36px)',
          mt: { xs: -2, md: -4 },
        }}
      >
        <StyledMapControlPanel
          showMapControlMobile={showMapControlMobile}
          id='map-controls'
        >
          <Box
            width={'100%'}
            sx={{
              backgroundColor: theme.palette.background.paper,
              zIndex: 1,
              top: 0,
              left: 0,
              position: { xs: 'fixed', md: 'relative' },
              p: { xs: 1, md: 0 },
            }}
          >
            <Button
              size='large'
              startIcon={<ChevronLeft />}
              color={'inherit'}
              sx={{ pl: 0, display: { xs: 'none', md: 'inline-flex' } }}
              onClick={() => {
                if (!hasError && feedId != null) {
                  navigate(`/feeds/${feedId}`);
                } else {
                  navigate('/');
                }
              }}
            >
              {t('common:back')}
            </Button>
            <Button
              size='large'
              color={'inherit'}
              sx={{ pl: 0, display: { xs: 'block', md: 'none' } }}
              onClick={() => {
                setShowMapControlMobile(!showMapControlMobile);
              }}
            >
              {t('fullMapView.closePanel')}
            </Button>
            <Box sx={{ display: { xs: 'block', md: 'none' } }}>
              {renderFilterChips()}
            </Box>
          </Box>

          <SearchHeader variant='h6' className='no-collapse'>
            {t('fullMapView.headers.routeTypes')}
          </SearchHeader>

          {isLoading ? (
            renderPanelSkeleton()
          ) : (
            <>
              <NestedCheckboxList
                checkboxData={getUniqueRouteTypesCheckboxData()}
                onCheckboxChange={(checkboxData: CheckboxStructure[]) => {
                  const nextTypeIds = checkboxData
                    .map((item) =>
                      item.checked ? item?.props?.routeTypeId ?? '' : '',
                    )
                    .filter((item) => item !== '');

                  setFilteredRouteTypeIds(nextTypeIds);

                  // Keep only route IDs that match the newly selected route types.
                  // If no type is selected, allow any route (don't force-clear).
                  if (nextTypeIds.length > 0) {
                    setFilteredRoutes((prev) =>
                      prev.filter((rid) =>
                        nextTypeIds.includes(getRouteType(rid) ?? ''),
                      ),
                    );
                  }
                }}
              />

              <SearchHeader variant='h6' className='no-collapse'>
                {t('fullMapView.headers.visibility')}
              </SearchHeader>
              <NestedCheckboxList
                checkboxData={[
                  {
                    title: t('fullMapView.hideStops'),
                    checked: hideStops,
                    type: 'checkbox',
                  },
                ]}
                onCheckboxChange={(checkboxData: CheckboxStructure[]) => {
                  setHideStops(checkboxData[0].checked);
                }}
              />

              <SearchHeader variant='h6' className='no-collapse'>
                {t('fullMapView.headers.routes')}
              </SearchHeader>
              <RouteSelector
                routes={
                  routes?.filter(
                    (r) =>
                      filteredRouteTypeIds.length === 0 ||
                      filteredRouteTypeIds.includes(r.routeType ?? ''),
                  ) ?? []
                }
                selectedRouteIds={filteredRoutes}
                onSelectionChange={(val) => {
                  // Ensure selections remain valid under the current type filter.
                  const filteredVal = val.filter(
                    (v) =>
                      filteredRouteTypeIds.length === 0 ||
                      filteredRouteTypeIds.includes(getRouteType(v) ?? ''),
                  );
                  setFilteredRoutes(filteredVal);
                }}
              />
              <Box
                id='mobile-control-action'
                sx={{
                  display: { xs: 'block', md: 'none' },
                  position: 'sticky',
                  bottom: '10px',
                }}
              >
                <Button
                  variant='contained'
                  fullWidth
                  onClick={() => {
                    setShowMapControlMobile(!showMapControlMobile);
                  }}
                >
                  {t('fullMapView.backToMap')}
                </Button>
              </Box>
            </>
          )}
        </StyledMapControlPanel>

        <Box
          sx={{
            width: '100%',
            position: 'relative',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {renderFilterChips()}

          <Box
            id='map-container'
            position={'relative'}
            sx={{
              mr: 2,
              borderRadius: '6px',
              border: `2px solid ${theme.palette.primary.main}`,
              overflow: 'hidden',
              flex: 1,
              ml: { xs: 2, md: 0 },
            }}
          >
            <Fab
              size='small'
              aria-label={t('fullMapView.aria.close')}
              sx={{ position: 'absolute', top: 10, right: 10, zIndex: 1000 }}
              onClick={() => {
                if (!hasError && feedId != null) {
                  navigate(`/feeds/${feedId}`);
                } else {
                  navigate('/');
                }
              }}
            >
              <CloseIcon />
            </Fab>
            <Fab
              size='small'
              aria-label={t('fullMapView.aria.refocus')}
              sx={{
                position: 'absolute',
                top: 10,
                right: { xs: 60 + 40 + 10, md: 60 },
                zIndex: 1000,
              }}
              disabled={hasError || feedId == null}
              onClick={() => {
                setRefocusTrigger(true);
                setTimeout(() => {
                  setRefocusTrigger(false);
                }, 500);
              }}
            >
              <CenterFocusStrong />
            </Fab>

            {/* Style FAB (opens overlay) */}
            <Fab
              size='small'
              aria-label={t('fullMapView.aria.mapStyle')}
              sx={{
                position: 'absolute',
                top: 10,
                right: { xs: 60 + (40 + 10) * 2, md: 110 },
                zIndex: 1000,
              }}
              onClick={() => {
                setStylePanelOpen((v) => !v);
              }}
            >
              <TuneIcon />
            </Fab>

            {/* Click-away overlay for style controls */}
            {stylePanelOpen && (
              <ClickAwayListener
                onClickAway={() => {
                  setStylePanelOpen(false);
                }}
              >
                <Box
                  sx={{
                    position: 'absolute',
                    top: 58,
                    right: { xs: 10, md: 10 },
                    zIndex: 1100,
                  }}
                >
                  <Paper
                    elevation={6}
                    sx={{
                      p: 1.5,
                      width: 300,
                      borderRadius: 2,
                      border: `1px solid ${theme.palette.divider}`,
                      backgroundColor: theme.palette.background.paper,
                    }}
                  >
                    <Typography
                      variant='subtitle2'
                      sx={{ fontWeight: 700, mb: 1 }}
                    >
                      {t('fullMapView.style.title')}
                    </Typography>

                    <Typography
                      variant='caption'
                      sx={{ color: theme.palette.text.secondary }}
                    >
                      {t('fullMapView.style.stopSize')}
                    </Typography>

                    <ToggleButtonGroup
                      exclusive
                      fullWidth
                      size='small'
                      value={stopPreset}
                      onChange={(_, val) => {
                        if (val == null) return;
                        setStopPreset(val);
                      }}
                      sx={{ mt: 0.5, mb: 1 }}
                    >
                      <ToggleButton value='small'>
                        {t('fullMapView.style.size.small')}
                      </ToggleButton>
                      <ToggleButton value='medium'>
                        {t('fullMapView.style.size.medium')}
                      </ToggleButton>
                      <ToggleButton value='large'>
                        {t('fullMapView.style.size.large')}
                      </ToggleButton>
                      <ToggleButton value='custom'>
                        {t('fullMapView.style.size.custom')}
                      </ToggleButton>
                    </ToggleButtonGroup>

                    {stopPreset === 'custom' && (
                      <Box sx={{ px: 0.5, pt: 0.5 }}>
                        <Slider
                          size='small'
                          value={customStopRadius}
                          min={2}
                          max={14}
                          step={1}
                          marks={[
                            { value: 2, label: '2' },
                            { value: 8, label: '8' },
                            { value: 14, label: '14' },
                          ]}
                          onChange={(_, v) => {
                            setCustomStopRadius(v as number);
                          }}
                          aria-label={t(
                            'fullMapView.style.customStopRadiusAria',
                          )}
                        />
                        <Typography
                          variant='caption'
                          sx={{ color: theme.palette.text.secondary }}
                        >
                          {t('fullMapView.style.radius', {
                            px: customStopRadius,
                          })}
                        </Typography>
                      </Box>
                    )}
                  </Paper>
                </Box>
              </ClickAwayListener>
            )}

            <Fab
              sx={{
                position: 'absolute',
                top: 10,
                right: 60,
                zIndex: 1000,
                display: { xs: 'inline-flex', md: 'none' },
              }}
              size='small'
              aria-label={t('fullMapView.aria.filter')}
              onClick={() => {
                setShowMapControlMobile(!showMapControlMobile);
              }}
            >
              <FilterAltIcon />
            </Fab>

            {isLoading && renderMapSkeleton()}

            {!isLoading && hasError && renderError()}

            {!isLoading &&
              !hasError &&
              config.enableGtfsVisualizationMap &&
              boundingBox != null && (
                <GtfsVisualizationMap
                  polygon={boundingBox}
                  latestDataset={latestDatasetLite}
                  visualizationId={
                    (feed as GTFSFeedType)?.visualization_dataset_id ??
                    latestDatasetLite?.id ??
                    ''
                  }
                  filteredRouteTypeIds={filteredRouteTypeIds}
                  filteredRoutes={filteredRoutes}
                  hideStops={hideStops}
                  dataDisplayLimit={config.visualizationMapFullDataLimit}
                  routes={routes}
                  refocusTrigger={refocusTrigger}
                  stopRadius={currentStopRadius}
                  preview={false}
                />
              )}
          </Box>
        </Box>
      </Box>
      <Alert severity='info' variant='outlined' sx={{ mt: 5, mx: 2 }}>
        <Typography variant='caption'>{t('fullMapView.dataBlurb')}</Typography>
      </Alert>
    </>
  );
}
