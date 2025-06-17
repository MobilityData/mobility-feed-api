import { Box, Fab } from '@mui/material';
import RouteSelector from '../../../components/RouteSelector';
import sampleRoutes from './sample-route-output.json';
import React, { useState } from 'react';
import { GtfsVisualizationMap } from '../../../components/GtfsVisualizationMap';
import CloseIcon from '@mui/icons-material/Close';
import NestedCheckboxList, {
  type CheckboxStructure,
} from '../../../components/NestedCheckboxList';
import { routeTypesMapping } from '../../../constants/RouteTypes';

export interface FullMapViewProps {}

export default function FullMapView({}: FullMapViewProps): React.ReactElement {
  const [filteredRoutes, setFilteredRoutes] = useState<string[]>([]);
  const [filteredRouteTypes, setFilteredRouteTypes] = useState<string[]>([]);

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
      checked: true,
      props: {
        routeTypeId: type,
      },
      type: 'checkbox',
    })) as CheckboxStructure[];
  };

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
      <Box display={'flex'} flexDirection={'row'} flexWrap={'wrap'}>
        <NestedCheckboxList
          checkboxData={[
            {
              title: 'Hide Stops',
              checked: false,
              type: 'checkbox',
            },
          ]}
          onCheckboxChange={(checkboxData: CheckboxStructure[]) => {
            console.log(checkboxData);
          }}
        />
        {/* Route type selector */}
        <Box sx={{ width: '300px', padding: 2 }}>
          <NestedCheckboxList
            checkboxData={getUniqueRouteTypesCheckboxData(sampleRoutes)}
            onCheckboxChange={(checkboxData: CheckboxStructure[]) => {
              setFilteredRouteTypes(
                checkboxData
                  .map((item) => {
                    return item.checked ? item?.props?.routeTypeId ?? '' : '';
                  })
                  .filter((item) => item !== ''),
              );
            }}
          />
        </Box>
        <RouteSelector
          routes={sampleRoutes}
          onSelectionChange={(val) => {
            setFilteredRoutes(val);
          }}
        ></RouteSelector>
      </Box>
      <Box sx={{ width: '100%', height: '90vh', position: 'relative' }}>
        <GtfsVisualizationMap
          polygon={bb as any}
          filteredRouteTypes={filteredRouteTypes}
          filteredRoutes={filteredRoutes}
        ></GtfsVisualizationMap>
      </Box>
    </Box>
  );
}
