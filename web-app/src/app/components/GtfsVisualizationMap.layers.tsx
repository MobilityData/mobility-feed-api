/* eslint-disable no-useless-escape */
/** Rule disabled due to data being stored with " that need to be escaped */

import {
  type ExpressionSpecification,
  type LayerSpecification,
} from 'maplibre-gl';
import { generateStopColorExpression } from './GtfsVisualizationMap.functions';
import { useTheme } from '@mui/material';

// layer helpers

export const routeTypeFilter = (
  filteredRouteTypeIds: string[],
): ExpressionSpecification | boolean =>
  filteredRouteTypeIds.length > 0
    ? ['in', ['get', 'route_type'], ['literal', filteredRouteTypeIds]]
    : true; // if no filter applied, show all

// Base filter for visible stops (main "stops" layer)
export const stopsBaseFilter = (
  hideStops: boolean,
  allSelectedRouteIds: string[],
): ExpressionSpecification | boolean => {
  // Base filter for visible stops (main "stops" layer)
  return hideStops
    ? false
    : allSelectedRouteIds.length === 0
      ? true // no filters → show all
      : [
          'any',
          ...allSelectedRouteIds.map(
            (id) =>
              [
                'in',
                `\"${id}\"`,
                ['get', 'route_ids'],
              ] as ExpressionSpecification, // route_ids stored as quoted-string list
          ),
        ];
};

// layers
export const RoutesWhiteLayer = (
  filteredRouteTypeIds: string[],
): LayerSpecification => {
  const theme = useTheme();
  return {
    id: 'routes-white',
    source: 'routes',
    filter: routeTypeFilter(filteredRouteTypeIds),
    'source-layer': 'routesoutput',
    type: 'line',
    paint: {
      'line-color': theme.palette.background.default,
      'line-width': ['match', ['get', 'route_type'], '3', 10, '1', 15, 3],
    },
  };
};

export const RouteLayer = (
  filteredRoutes: string[],
  filteredRouteTypeIds: string[],
): LayerSpecification => {
  return {
    id: 'routes',
    filter: routeTypeFilter(filteredRouteTypeIds),
    source: 'routes',
    'source-layer': 'routesoutput',
    type: 'line',
    paint: {
      'line-color': ['concat', '#', ['get', 'route_color']],
      'line-width': ['match', ['get', 'route_type'], '3', 1, '1', 4, 3],
      'line-opacity': [
        'case',
        [
          'any',
          ['==', filteredRoutes.length, 0],
          ['in', ['get', 'route_id'], ['literal', filteredRoutes]],
        ],
        0.4,
        0.1,
      ],
    },
    layout: {
      'line-sort-key': ['match', ['get', 'route_type'], '1', 3, '3', 2, 0],
    },
  };
};

export const StopLayer = (
  hideStops: boolean,
  allSelectedRouteIds: string[],
  stopRadius: number,
): LayerSpecification => {
  return {
    id: 'stops',
    filter: stopsBaseFilter(hideStops, allSelectedRouteIds),
    source: 'sample',
    'source-layer': 'stopsoutput',
    type: 'circle',
    paint: {
      'circle-radius': stopRadius,
      'circle-color': '#000000',
      'circle-opacity': 0.4,
    },
    minzoom: 12,
    maxzoom: 22,
  };
};

export const RouteHighlightLayer = (
  routeId: string | undefined,
  hoverInfo: string[],
  filteredRoutes: string[],
): LayerSpecification => {
  return {
    id: 'routes-highlight',
    source: 'routes',
    'source-layer': 'routesoutput',
    type: 'line',
    paint: {
      'line-color': ['concat', '#', ['get', 'route_color']],
      'line-opacity': 1,
      'line-width': ['match', ['get', 'route_type'], '3', 5, '1', 6, 3],
    },
    filter: [
      'any',
      ['in', ['get', 'route_id'], ['literal', hoverInfo]],
      ['in', ['get', 'route_id'], ['literal', filteredRoutes]],
      ['in', ['get', 'route_id'], ['literal', routeId ?? '']],
    ],
  };
};

export const StopsHighlightLayer = (
  hoverInfo: string[],
  hideStops: boolean,
  filteredRoutes: string[],
  stopId: string | undefined,
  stopHighlightColorMap: Record<string, string>,
): LayerSpecification => {
  return {
    id: 'stops-highlight',
    source: 'sample',
    'source-layer': 'stopsoutput',
    type: 'circle',
    paint: {
      'circle-radius': 7,
      'circle-color': generateStopColorExpression(stopHighlightColorMap),
      'circle-opacity': 1,
    },
    minzoom: 10,
    maxzoom: 22,
    filter: hideStops
      ? !hideStops
      : [
          'any',
          ['in', ['get', 'stop_id'], ['literal', hoverInfo]],
          ['==', ['get', 'stop_id'], ['literal', stopId ?? '']],
          [
            'any',
            ...filteredRoutes.map((id) => {
              return [
                'in',
                `\"${id}\"`,
                ['get', 'route_ids'],
              ] as ExpressionSpecification;
            }),
          ],
          [
            'any',
            ...hoverInfo.map((id) => {
              return [
                'in',
                `\"${id}\"`,
                ['get', 'route_ids'],
              ] as ExpressionSpecification;
            }),
          ],
        ],
  };
};

export const StopsHighlightOuterLayer = (
  hoverInfo: string[],
  hideStops: boolean,
  filteredRoutes: string[],
): LayerSpecification => {
  const theme = useTheme();
  return {
    id: 'stops-highlight-outer',
    source: 'sample',
    'source-layer': 'stopsoutput',
    type: 'circle',
    paint: {
      'circle-radius': 3,
      'circle-color': theme.palette.background.paper,
      'circle-opacity': 1,
    },
    filter: hideStops
      ? !hideStops
      : [
          'any',
          ['in', ['get', 'stop_id'], ['literal', hoverInfo]],
          [
            'any',
            ...filteredRoutes.map((id) => {
              return [
                'in',
                `\"${id}\"`,
                ['get', 'route_ids'],
              ] as ExpressionSpecification;
            }),
          ],
          [
            'any',
            ...hoverInfo.map((id) => {
              return [
                'in',
                `\"${id}\"`,
                ['get', 'route_ids'],
              ] as ExpressionSpecification;
            }),
          ],
        ],
  };
};

export const StopsIndexLayer = (): LayerSpecification => {
  return {
    id: 'stops-index',
    source: 'sample',
    'source-layer': 'stopsoutput',
    type: 'circle',
    paint: {
      'circle-opacity': 0,
      'circle-radius': 5,
    },
  };
};
