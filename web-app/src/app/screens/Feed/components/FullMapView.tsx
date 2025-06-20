import { Box, Fab, Button, Chip, useTheme } from '@mui/material';
import RouteSelector from '../../../components/RouteSelector';
import sampleRoutes from './sample-route-output.json';
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

export default function FullMapView(): React.ReactElement {
  const { t } = useTranslation('feeds');
  const theme = useTheme();
  const [filteredRoutes, setFilteredRoutes] = useState<string[]>([]);
  const [filteredRouteTypes, setFilteredRouteTypes] = useState<string[]>([]);
  const [hideStops, setHideStops] = useState<boolean>(false);

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
      title: routeTypesMapping[type],
      checked: filteredRouteTypes.includes(routeTypesMapping[type]),
      props: {
        routeTypeId: type,
      },
      type: 'checkbox',
    })) as CheckboxStructure[];
  };

  // TODO: this is hardcoded for Montreal, should be dynamic
  const bb = [
    [45.402668, -73.956204],
    [45.402668, -73.480581],
    [45.701116, -73.480581],
    [45.701116, -73.956204],
  ];
  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        position: 'relative',
        display: 'flex',
        pt: 1,
        minHeight: 'calc(100vh - 64px - 36px)', // Adjusts for the height of the header and any additional padding
        mt: { xs: -2, md: -4 }, // Adjusts for the margin of the header
      }}
    >
      <Box id='map-controls' sx={{ width: '300px', padding: 2, pt: 0 }}>
        <Box width={'100%'}>
          <Button
            size='large'
            startIcon={<ChevronLeft />}
            color={'inherit'}
            sx={{ pl: 0 }}
            onClick={() => {
              window.history.back();
            }}
          >
            {t('common:back')}
          </Button>
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
          Routes
        </SearchHeader>
        <RouteSelector
          routes={sampleRoutes}
          selectedRouteIds={filteredRoutes}
          onSelectionChange={(val) => {
            setFilteredRoutes(val);
          }}
        ></RouteSelector>
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
      </Box>
      <Box
        sx={{
          width: '100%',
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Box
          id='map-filters'
          display={'flex'}
          flexWrap={'wrap'}
          alignItems={'center'}
          gap={1}
          sx={{ p: 1, minHeight: '50px' }}
        >
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
                setFilteredRoutes((prev) =>
                  prev.filter((id) => id !== routeId),
                );
              }}
              sx={{ cursor: 'pointer' }}
            ></Chip>
          ))}

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
        </Box>
        <Box
          id='map-container'
          position={'relative'}
          sx={{
            mr: 2,
            borderRadius: '6px',
            border: `2px solid ${theme.palette.primary.main}`,
            overflow: 'hidden',
            flex: 1,
          }}
        >
          <Fab
            size='small'
            aria-label='add'
            sx={{ position: 'absolute', top: 10, right: 10, zIndex: 1000 }}
            onClick={() => {
              window.history.back();
            }}
          >
            <CloseIcon />
          </Fab>
          <GtfsVisualizationMap
            polygon={bb as any}
            filteredRouteTypes={filteredRouteTypes}
            filteredRoutes={filteredRoutes}
            hideStops={hideStops}
          ></GtfsVisualizationMap>
        </Box>
      </Box>
    </Box>
  );
}
