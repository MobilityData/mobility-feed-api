import { Box, Fab, Button, Chip, useTheme } from '@mui/material';
import RouteSelector from '../../../components/RouteSelector';
import React, { useState } from 'react';
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
  selectGtfsDatasetRoutesJson,
  selectGtfsDatasetRouteTypes,
  selectGtfsFeedBoundingBox,
  selectLatestDatasetsData,
} from '../../../store/selectors';
import { useSelector } from 'react-redux';
import { useParams } from 'react-router-dom';
import { loadingDataset } from '../../../store/dataset-reducer';
import { useAppDispatch } from '../../../hooks';
import { useRemoteConfig } from '../../../context/RemoteConfigProvider';
import { getRouteTypeTranslatedName } from '../../../constants/RouteTypes';

export default function FullMapView(): React.ReactElement {
  const { t } = useTranslation('feeds');
  const { feedId } = useParams();
  const theme = useTheme();
  const [filteredRoutes, setFilteredRoutes] = useState<string[]>([]);
  const [filteredRouteTypeIds, setFilteredRouteTypeIds] = useState<string[]>(
    [],
  );
  const [hideStops, setHideStops] = useState<boolean>(false);
  const [showMapControlMobile, setShowMapControlMobile] =
    useState<boolean>(false);
  const { config } = useRemoteConfig();
  const latestDataset = useSelector(selectLatestDatasetsData);
  const boundingBox = useSelector(selectGtfsFeedBoundingBox);
  const routes = useSelector(selectGtfsDatasetRoutesJson);
  const routeTypes = useSelector(selectGtfsDatasetRouteTypes);
  const dispatch = useAppDispatch();

  const clearAllFilters = (): void => {
    setFilteredRoutes([]);
    setFilteredRouteTypeIds([]);
    setHideStops(false);
  };

  const getRouteDisplayName = (routeId: string): string => {
    const route = (routes ?? []).find((r) => r.routeId === routeId);
    return route != null ? `${route.routeId} - ${route.routeName}` : routeId;
  };

  const getUniqueRouteTypesCheckboxData = (): CheckboxStructure[] => {
    return (routeTypes ?? []).map((routeTypeId) => {
      const translatedName = getRouteTypeTranslatedName(routeTypeId, t);
      return {
        title: translatedName,
        checked: filteredRouteTypeIds.includes(routeTypeId),
        props: {
          routeTypeId,
        },
        type: 'checkbox',
      };
    }) as CheckboxStructure[];
  };

  if (boundingBox == undefined && latestDataset == undefined) {
    if (feedId != undefined) {
      dispatch(
        loadingDataset({
          feedId,
          limit: 1,
        }),
      );
    }
  }

  const renderFilterChips = (): React.ReactElement => {
    return (
      <StyledChipFilterContainer id='map-filters'>
        {(filteredRoutes.length > 0 ||
          filteredRouteTypeIds.length > 0 ||
          hideStops) && (
          <Button
            variant={'text'}
            onClick={clearAllFilters}
            size={'small'}
            color={'primary'}
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
          ></Chip>
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
          ></Chip>
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
          ></Chip>
        ))}
      </StyledChipFilterContainer>
    );
  };

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
              window.history.back();
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
        <NestedCheckboxList
          checkboxData={getUniqueRouteTypesCheckboxData()}
          onCheckboxChange={(checkboxData: CheckboxStructure[]) => {
            setFilteredRouteTypeIds(
              checkboxData
                .map((item) => {
                  return item.checked ? item?.props?.routeTypeId ?? '' : '';
                })
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
        ></RouteSelector>
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
              window.history.back();
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
          {config.enableGtfsVisualizationMap && boundingBox != undefined && (
            <GtfsVisualizationMap
              polygon={boundingBox}
              latestDataset={latestDataset}
              filteredRouteTypeIds={filteredRouteTypeIds}
              filteredRoutes={filteredRoutes}
              hideStops={hideStops}
            ></GtfsVisualizationMap>
          )}
        </Box>
      </Box>
    </Box>
  );
}
