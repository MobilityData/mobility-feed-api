import { Box, Fab } from '@mui/material';
import RouteSelector from '../../../components/RouteSelector';
import sampleRoutes from './sample-route-output.json';
import { useState } from 'react';
import { GtfsVisualizationMap } from '../../../components/GtfsVisualizationMap';
import CloseIcon from '@mui/icons-material/Close';

export interface FullMapViewProps {}

export default function FullMapView({}: FullMapViewProps): React.ReactElement {
  const [filteredRoutes, setFilteredRoutes] = useState<string[]>([]);
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
        flexDirection: 'column',
      }}
    >
      <Fab
        size='small'
        aria-label='add'
        sx={{ position: 'absolute', top: 10, right: 10, zIndex: 1000 }}
        onClick={() => window.history.back()}
      >
        <CloseIcon />
      </Fab>
      <RouteSelector
        routes={sampleRoutes}
        onSelectionChange={(val) => setFilteredRoutes(val)}
      ></RouteSelector>
      <Box sx={{ width: '100%', height: '90vh', position: 'relative' }}>
        <GtfsVisualizationMap
          polygon={bb as any}
          filteredRoutes={filteredRoutes}
        ></GtfsVisualizationMap>
      </Box>
    </Box>
  );
}
