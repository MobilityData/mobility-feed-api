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
} from '@mui/material';
import RouteSelector from '../../../components/RouteSelector';
import React, { useEffect, useMemo, useState } from 'react';
import { GtfsVisualizationMap } from '../../../components/GtfsVisualizationMap';
import CloseIcon from '@mui/icons-material/Close';
import NestedCheckboxList, {
  type CheckboxStructure,
} from '../../../components/NestedCheckboxList';
import { ChevronLeft } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { SearchHeader } from '../../../styles/Filters.styles';
import FilterAltIcon from '@mui/icons-material/FilterAlt';
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
  selectGtfsFeedBoundingBox,
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

export default function FullMapView(): React.ReactElement {
  const { t } = useTranslation('feeds');
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

  const { config } = useRemoteConfig();
  const gtfsFeed = useSelector(selectFeedData) as GTFSFeedType | undefined;
  const latestDatasetLite = {
    hosted_url: gtfsFeed?.latest_dataset?.hosted_url,
    id: gtfsFeed?.latest_dataset?.id,
  };
  const boundingBox = useSelector(selectGtfsFeedBoundingBox);
  const routes = useSelector(selectGtfsDatasetRoutesJson);
  const routeTypes = useSelector(selectGtfsDatasetRouteTypes);

  const [filteredRoutes, setFilteredRoutes] = useState<string[]>([]);
  const [filteredRouteTypeIds, setFilteredRouteTypeIds] = useState<string[]>(
    [],
  );
  const [hideStops, setHideStops] = useState<boolean>(false);
  const [showMapControlMobile, setShowMapControlMobile] =
    useState<boolean>(false);

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
  }, [feedError, routesError, isGtfsFeed, feed, missingBboxAfterLoad]);

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
          Clear All
        </Button>
      )}
      {hideStops && (
        <Chip
          color='primary'
          variant='outlined'
          size='small'
          label='Hide Stops'
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

  return (
    <Box
      sx={{
        width: '100%',
        position: 'relative',
        display: 'flex',
        pt: 1,
        height: 'calc(100vh - 64px - 36px)', // Adjusts for the height of the header and any additional padding
        mt: { xs: -2, md: -4 }, // Adjusts for the margin of the header
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
            Close
          </Button>
          <Box sx={{ display: { xs: 'block', md: 'none' } }}>
            {renderFilterChips()}
          </Box>
        </Box>

        <SearchHeader variant='h6' className='no-collapse'>
          Route Types
        </SearchHeader>

        {isLoading ? (
          renderPanelSkeleton()
        ) : (
          <>
            <NestedCheckboxList
              checkboxData={getUniqueRouteTypesCheckboxData()}
              onCheckboxChange={(checkboxData: CheckboxStructure[]) => {
                setFilteredRouteTypeIds(
                  checkboxData
                    .map((item) =>
                      item.checked ? item?.props?.routeTypeId ?? '' : '',
                    )
                    .filter((item) => item !== ''),
                );
              }}
            />

            <SearchHeader variant='h6' className='no-collapse'>
              Visibility
            </SearchHeader>
            <NestedCheckboxList
              checkboxData={[
                {
                  title: 'Hide Stops',
                  checked: hideStops,
                  type: 'checkbox',
                },
              ]}
              onCheckboxChange={(checkboxData: CheckboxStructure[]) => {
                setHideStops(checkboxData[0].checked);
              }}
            />

            <SearchHeader variant='h6' className='no-collapse'>
              Routes
            </SearchHeader>
            <RouteSelector
              routes={routes ?? []}
              selectedRouteIds={filteredRoutes}
              onSelectionChange={(val) => {
                setFilteredRoutes(val);
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
                Back To Map
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
            aria-label='close'
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
            sx={{
              position: 'absolute',
              top: 10,
              right: 70,
              zIndex: 1000,
              display: { xs: 'inline-flex', md: 'none' },
            }}
            size='small'
            aria-label='filter'
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
                filteredRouteTypeIds={filteredRouteTypeIds}
                filteredRoutes={filteredRoutes}
                hideStops={hideStops}
              />
            )}
        </Box>
      </Box>
    </Box>
  );
}
