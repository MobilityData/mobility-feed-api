import { Box, Fab, Button, Chip, useTheme } from '@mui/material';
import RouteSelector from '../../../components/RouteSelector';
import sampleRoutes from './sample-route-output.json'; // STM
//import sampleRoutes from './routes_TBM-2622_sample.json'; // BOrdaux
import React, { useState } from 'react';
import { GtfsVisualizationMap } from '../../../components/GtfsVisualizationMap';
import CloseIcon from '@mui/icons-material/Close';
import NestedCheckboxList, {
  type CheckboxStructure,
} from '../../../components/NestedCheckboxList';
import { routeTypesMapping } from '../../../constants/RouteTypes';
import { ChevronLeft } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { SearchHeader } from '../../../styles/Filters.styles';
import FilterAltIcon from '@mui/icons-material/FilterAlt';
import {
  StyledChipFilterContainer,
  StyledMapControlPanel,
} from '../Map.styles';
import {
  selectBoundingBoxFromLatestDataset,
  selectDatasetsLoadingStatus,
  selectLatestDatasetsData,
} from '../../../store/selectors';
import { useSelector } from 'react-redux';
import { useParams } from 'react-router-dom';
import { loadingDataset } from '../../../store/dataset-reducer';
import { useAppDispatch } from '../../../hooks';

export default function FullMapView(): React.ReactElement {
  const { t } = useTranslation('feeds');
  const { feedId, feedDataType } = useParams();
  const theme = useTheme();
  const [filteredRoutes, setFilteredRoutes] = useState<string[]>([]);
  const [filteredRouteTypes, setFilteredRouteTypes] = useState<string[]>([]);
  const [hideStops, setHideStops] = useState<boolean>(false);
  const [showMapControlMobile, setShowMapControlMobile] =
    useState<boolean>(false);
  const latestDataset = useSelector(selectLatestDatasetsData);
  const boundingBox = useSelector(selectBoundingBoxFromLatestDataset);
  const datasetLoadingStatus = useSelector(selectDatasetsLoadingStatus);
  const dispatch = useAppDispatch();

  const clearAllFilters = (): void => {
    setFilteredRoutes([]);
    setFilteredRouteTypes([]);
    setHideStops(false);
  };

  const getRouteDisplayName = (routeId: string): string => {
    const route = sampleRoutes.find((r) => r.routeId === routeId);
    return route != null ? `${route.routeId} - ${route.routeName}` : routeId;
  };

  const getUniqueRouteTypesCheckboxData = (
    routes: Array<{ routeType: string }>,
  ): CheckboxStructure[] => {
    const uniqueTypes = new Set<string>();
    routes.forEach((route) => {
      if (route?.routeType !== '') {
        uniqueTypes.add(route.routeType);
      }
    });
    return Array.from(uniqueTypes).map((type) => ({
      title: routeTypesMapping[type].name,
      checked: filteredRouteTypes.includes(routeTypesMapping[type].name),
      props: {
        routeTypeId: type,
      },
      type: 'checkbox',
    })) as CheckboxStructure[];
  };

  // since this is a page on it's own, we can check if the bounding box is set in state, if not we have no choice but to fetch it
  // console.log(
  //   'boundingBox from state',
  //   boundingBox,
  //   latestDataset,
  //   datasetLoadingStatus,
  //   feedId,
  // );
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
          filteredRouteTypes.length > 0 ||
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
        {filteredRouteTypes.map((routeType) => (
          <Chip
            color='primary'
            variant='outlined'
            size='small'
            key={routeType}
            label={routeType}
            onDelete={() => {
              setFilteredRouteTypes((prev) =>
                prev.filter((type) => type !== routeType),
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
          checkboxData={getUniqueRouteTypesCheckboxData(sampleRoutes)}
          onCheckboxChange={(checkboxData: CheckboxStructure[]) => {
            setFilteredRouteTypes(
              checkboxData
                .map((item) => {
                  return item.checked ? item?.title ?? '' : '';
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
          routes={sampleRoutes}
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
            onClick={() => setShowMapControlMobile(!showMapControlMobile)}
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
            onClick={() => setShowMapControlMobile(!showMapControlMobile)}
          >
            <FilterAltIcon />
          </Fab>
          {boundingBox != undefined && (
            <GtfsVisualizationMap
              polygon={boundingBox}
              filteredRouteTypes={filteredRouteTypes}
              filteredRoutes={filteredRoutes}
              hideStops={hideStops}
            ></GtfsVisualizationMap>
          )}
        </Box>
      </Box>
    </Box>
  );
}
