/* eslint-disable */

import { useEffect, useRef, useState, useMemo } from 'react';
import Map, {
  type MapRef,
  MapProvider,
  NavigationControl,
  ScaleControl,
} from 'react-map-gl/maplibre';
import maplibregl, {
  type ExpressionSpecification,
  type LngLatBoundsLike,
} from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Protocol } from 'pmtiles';
import { type LatLngExpression } from 'leaflet';
import type { FeatureCollection } from 'geojson';
import { Box, useTheme } from '@mui/material';
import { MapElement, MapRouteElement, MapStopElement } from './MapElement';
import {
  reversedRouteTypesMapping,
} from '../constants/RouteTypes';
import { MapDataPopup } from './Map/MapDataPopup';
import { useTheme as themeProvider } from '../context/ThemeProvider';

interface LatestDatasetLite {
  hosted_url?: string;
  id?: string;
  stable_id?: string;
}

export interface GtfsVisualizationMapProps {
  polygon: LatLngExpression[];
  latestDataset?: LatestDatasetLite;
  filteredRoutes?: string[];
  filteredRouteTypes?: string[];
  hideStops?: boolean;
}

export const GtfsVisualizationMap = ({
  polygon,
  latestDataset,
  filteredRoutes = [],
  filteredRouteTypes = [],
  hideStops = false,
}: GtfsVisualizationMapProps): JSX.Element => {

    console.log('[GtfsVisualizationMap] mount', {
        latestDatasetId: latestDataset?.id,
        latestDatasetHostedUrl: latestDataset?.hosted_url,
    });

    const { stopsPmtilesUrl, routesPmtilesUrl } = useMemo(() => {
    const baseUrl = latestDataset?.hosted_url ? latestDataset.hosted_url.replace(/[^/]+$/, '') : undefined;
    console.log('[GtfsVisualizationMap] latestDataset URLs', {
        hostedUrl: latestDataset?.hosted_url,
        baseUrl,
    });

     const stops = `${baseUrl}/pmtiles/stops.pmtiles`;
     const routes = `${baseUrl}/pmtiles/routes.pmtiles`;

     return { stopsPmtilesUrl: stops, routesPmtilesUrl: routes };
  }, [latestDataset?.id, latestDataset?.stable_id]);


    useEffect(() => {
      console.log('[GtfsVisualizationMap] PMTiles URLs', {
        stopsPmtilesUrl,
        routesPmtilesUrl,
      });
    }, [stopsPmtilesUrl, routesPmtilesUrl]);

        // Log whenever the identifiers change
  useEffect(() => {
    console.log('[GtfsVisualizationMap] props update', {
      latestDatasetId: latestDataset?.id,
    });
  }, [latestDataset?.id]);

  const theme = useTheme();
  const [hoverInfo, setHoverInfo] = useState<string[]>([]);
  const [hoverData, setHoverData] = useState<string>('');
  const [mapElement, setMapElement] = useState<MapElement[]>([]);
  const [mapClickRouteData, setMapClickRouteData] = useState<Record<
    string,
    string
  > | null>(null);
  const [mapClickStopData, setMapClickStopData] = useState<Record<
    string,
    string
  > | null>(null);
  const mapRef = useRef<MapRef>(null);

  const filteredRouteTypesIds = filteredRouteTypes.map(
    (d) => reversedRouteTypesMapping[d],
  );

  // Create a map to store routeId to routeColor mapping
  const routeIdToColorMap: Record<string, string> = {};
  mapElement.forEach((el) => {
    if (!el.isStop) {
      const routeElement: MapRouteElement = el as MapRouteElement;
      if (routeElement.routeId && routeElement.routeColor) {
        routeIdToColorMap[routeElement.routeId] = routeElement.routeColor;
      }
    }
  });

  function generateStopColorExpression(
    routeIdToColor: Record<string, string>,
    fallback = '#888',
  ): ExpressionSpecification {
    const expression: any[] = ['case'];

    Object.entries(routeIdToColor).forEach(([routeId, color]) => {
      expression.push(
        ['in', `"${routeId}"`, ['get', 'route_ids']],
        `#${color}`,
      );
    });

    // If no conditions added, just return a fallback color directly
    if (expression.length === 1) {
      return fallback as unknown as ExpressionSpecification;
    }

    expression.push(fallback); // Add fallback color
    return expression as ExpressionSpecification;
  }

  const routeTypeFilter: ExpressionSpecification | boolean =
    filteredRouteTypes.length > 0
      ? ['in', ['get', 'route_type'], ['literal', filteredRouteTypesIds]]
      : true; // if no filter applied, show all

  const handleMouseClick = (event: maplibregl.MapLayerMouseEvent): void => {
    const map = mapRef.current?.getMap();
    if (map != undefined) {
      // Get the features under the mouse pointer
      const features = map.queryRenderedFeatures(event.point, {
        layers: ['stops-highlight', 'routes-highlight'], // Change this to your actual layer ID
      });

      const selectedStop = features.find(
        (feature) => feature.layer.id === 'stops-highlight',
      );
      if (selectedStop != undefined) {
        setMapClickStopData({
          ...selectedStop.properties,
          longitude: String(event.lngLat.lng),
          latitude: String(event.lngLat.lat),
        }); // Example properties, adjust as needed
        console.log('Mouse selectedStop', selectedStop);
        setMapClickRouteData(null);
        return;
      }

      const selectedRoute = features.find(
        (feature) => feature.layer.id === 'routes-highlight',
      );
      if (selectedRoute != undefined) {
        setMapClickRouteData({
          ...selectedRoute.properties,
          longitude: String(event.lngLat.lng),
          latitude: String(event.lngLat.lat),
        }); // Example properties, adjust as needed
        console.log('Mouse clicked on map:', features);
        setMapClickStopData(null);
      }
    }
  };

  const handlePopupClose = () => {
    setMapClickRouteData(null);
    setMapClickStopData(null);
  };

  const handleMouseMove = (event: maplibregl.MapLayerMouseEvent): void => {
    // Ensure that the mapRef is not null before trying to access the map
    const map = mapRef.current?.getMap();
    const mapElements: MapElement[] = [];

    if (map != undefined) {
      // Get the features under the mouse pointer
      const features = map.queryRenderedFeatures(event.point, {
        layers: ['stops', 'routes', 'routes-white', 'stops-highlight'], // Change this to your actual layer ID
      });

      if (
        features.length > 0 ||
        mapClickRouteData != null ||
        mapClickStopData != null
      ) {
        if (mapClickRouteData != null) {
          const mapElement: MapRouteElement = {
            isStop: false,
            name: mapClickRouteData.route_long_name,
            routeType: Number(mapClickRouteData.route_type),
            routeColor: mapClickRouteData.route_color,
            routeTextColor: mapClickRouteData.route_text_color,
            routeId: mapClickRouteData.route_id,
          };
          mapElements.push(mapElement);
        }
        if (mapClickStopData != null) {
          const mapElement: MapStopElement = {
            isStop: true,
            name: mapClickStopData.stop_name,
            locationType: Number(mapClickStopData.location_type),
            stopId: mapClickStopData.stop_id,
          };
          mapElements.push(mapElement);
        }
        features.forEach((feature) => {
          if (
            feature.layer.id === 'stops' ||
            feature.layer.id === 'stops-highlight'
          ) {
            const mapElement: MapStopElement = {
              isStop: true,
              name: feature.properties.stop_name,
              locationType: Number(feature.properties.location_type),
              stopId: feature.properties.stop_id,
            };
            mapElements.push(mapElement);
          } else {
            const mapElement: MapElement = {
              isStop: false,
              name: feature.properties.route_long_name,
              routeType: feature.properties.route_type,
              routeColor: feature.properties.route_color,
              routeTextColor: feature.properties.route_text_color,
              routeId: feature.properties.route_id,
            };
            mapElements.push(mapElement);
          }
        });

        setMapElement(mapElements);

        const elementIds: string[] = [];
        features.forEach((feature) => {
          if (feature.properties.route_id != undefined) {
            elementIds.push(feature.properties.route_id);
          } else {
            elementIds.push(feature.properties.stop_id);
          }
        });
        setHoverInfo(elementIds);
      } else {
        setHoverInfo([]);
        setHoverData('');
        setMapElement([]);
      }
    }
  };

  useEffect(() => {
    // Will be called on add statup only once
    const protocol = new Protocol();
    maplibregl.addProtocol('pmtiles', protocol.tile);
    return () => {
      maplibregl.removeProtocol('pmtiles');
    };
  }, []);

  const getBoundsFromCoordinates = (
    coordinates: Array<[number, number]>,
  ): LngLatBoundsLike => {
    let minLng = Number.POSITIVE_INFINITY;
    let minLat = Number.POSITIVE_INFINITY;
    let maxLng = Number.NEGATIVE_INFINITY;
    let maxLat = Number.NEGATIVE_INFINITY;

    coordinates.forEach(([lat, lng]) => {
      minLat = Math.min(minLat, lat);
      maxLat = Math.max(maxLat, lat);
      minLng = Math.min(minLng, lng);
      maxLng = Math.max(maxLng, lng);
    });

    return [minLng, minLat, maxLng, maxLat]; // Matches LngLatBoundsLike format
  };

  const bounds: LngLatBoundsLike = getBoundsFromCoordinates(
    polygon as Array<[number, number]>,
  );

  // in polygon: IMPORTANT - the coordinates are in the format [lat, lng] (not [lng, lat])
  const boundingBoxFormmated = polygon.map((point: any) => [
    point[1],
    point[0],
  ]);

  // TODO: example of how to use geojson in maplibre (stop density)
  const geojson: FeatureCollection = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: {},
        geometry: {
          type: 'Polygon',
          coordinates: [boundingBoxFormmated],
        },
      },
    ],
  };

  return (
    <MapProvider>
      <Box sx={{ display: 'flex', height: '100%' }}>
        <Box
          sx={{
            width: '100%',
            height: '100%',
            position: 'relative',
            borderColor: theme.palette.primary.main,
            borderRadius: '5px',
          }}
        >
          <MapElement mapElements={mapElement}></MapElement>
          <Map
            onClick={(event) => {
              handleMouseClick(event);
            }}
            ref={mapRef}
            onMouseMove={(event) => {
              handleMouseMove(event);
            }}
            style={{ width: '100%', height: '100%' }}
            initialViewState={{ bounds }}
            interactiveLayerIds={[
              'stops',
              'routes',
              'routes-white',
              'routes-highlight',
              'stops-highlight',
            ]}
            scrollZoom={true}
            dragPan={true}
            // https://pmtiles.io/ Good tool for debugging PMTiles
            mapStyle={{
              version: 8,
              sources: {
                'raster-tiles': {
                  type: 'raster',
                  tiles: [theme.map.basemapTileUrl],
                  tileSize: 256,
                  attribution:
                    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                },
                sample: {
                  type: 'vector',
                    url: `pmtiles://${stopsPmtilesUrl}`, // dynamic stops
                  //url: 'pmtiles://https://storage.googleapis.com/map-details-bucket-test/stops-bordeaux.pmtiles', // bordeaux
                },
                routes: {
                  type: 'vector',
                url: `pmtiles://${routesPmtilesUrl}`, // dynamic routes
                  //url: 'pmtiles://https://storage.googleapis.com/map-details-bucket-test/routes-bordeaux.pmtiles', // bordeaux
                },
                // boundingBox: {
                //   type: 'geojson',
                //   data: geojson, // displays the bounding box
                // },
              },
              // Order matters: the last layer will be on top
              // Layers control all the logic in the map -> lots of duplicated for the sake of effects
              layers: [
                {
                  id: 'simple-tiles',
                  type: 'raster',
                  source: 'raster-tiles',
                  minzoom: 0,
                  maxzoom: 22,
                },
                {
                  id: 'routes-white', // white padding on the route lines
                  source: 'routes',
                  filter: routeTypeFilter,
                  'source-layer': 'routesoutput', // Name of the geojson file when converting to pmtile. route-output.geojson -> routesoutput
                  type: 'line',
                  paint: {
                    // style and color of the stops
                    'line-color': theme.palette.background.paper,
                    'line-width': [
                      'match',
                      ['get', 'route_type'], // Property from the vector tile
                      '3',
                      4, // 3 = bus
                      '1',
                      15, // 1 = metro
                      3, // Default width
                    ],
                  },
                },
                {
                  id: 'routes',
                  filter: routeTypeFilter,
                  source: 'routes',
                  'source-layer': 'routesoutput', // Name of the geojson file when converting to pmtile. route-output.geojson -> routesoutput
                  type: 'line',
                  paint: {
                    // style and color of the stops
                    'line-color': ['concat', '#', ['get', 'route_color']],
                    'line-width': [
                      // line with thickness based on route type (thicker for metro, thinner for bus)
                      'match',
                      ['get', 'route_type'], // Property from the vector tile
                      '3',
                      1, // 3 = bus
                      '1',
                      4, // 1 = metro
                      3, // Default width
                    ],
                    'line-opacity': [
                      // Opacity based on whether the route is selected or not
                      'case',
                      [
                        'any',
                        ['==', filteredRoutes.length, 0],
                        [
                          'in',
                          ['get', 'route_id'],
                          ['literal', filteredRoutes],
                        ],
                      ],
                      0.4, // default opacity if selected or no filter
                      0.1, // faded if NOT in filteredRoutes
                    ],
                  },
                  // If routeTypesFilter includes a value -> show that
                  // If routeTypesFilter is empty -> show all
                  layout: {
                    'line-sort-key': [
                      'match',
                      ['get', 'route_type'],
                      '1',
                      3, // metro on top
                      '3',
                      2, // bus second
                      0, // Default priority
                    ],
                  },
                },

                // {
                //   id: 'boundingBox',
                //   type: 'fill',
                //   source: 'boundingBox',
                //   paint: {
                //     'fill-color': '#088',
                //     'fill-opacity': 0.8,
                //   },
                // },
                {
                  id: 'stops',
                  filter: !hideStops, // Hide stops if hideStops is true
                  source: 'sample',
                  'source-layer': 'stopsoutput', // Name of the geojson file when converting to pmtile. stops-output.geojson -> stopssoutput
                  type: 'circle',
                  paint: {
                    // style and color of the stops
                    'circle-radius': 3,
                    'circle-color': '#000000',
                    'circle-opacity': 0.4,
                  },
                  minzoom: 12,
                  maxzoom: 22,
                },
                {
                  id: 'routes-highlight',
                  source: 'routes',
                  'source-layer': 'routesoutput', // Name of the geojson file when converting to pmtile. stops-output.geojson -> stopssoutput
                  type: 'line',
                  paint: {
                    // style and color of the stops
                    'line-color': ['concat', '#', ['get', 'route_color']],
                    'line-opacity': 1,
                    'line-width': [
                      'match',
                      ['get', 'route_type'], // Property from the vector tile
                      '3',
                      5, // 3 = bus
                      '1',
                      6, // 1 = metro
                      3, // Default width
                    ],
                  },

                  filter: [
                    'any',
                    ['in', ['get', 'route_id'], ['literal', hoverInfo]],
                    ['in', ['get', 'route_id'], ['literal', filteredRoutes]],
                    [
                      'in',
                      ['get', 'route_id'],
                      ['literal', mapClickRouteData?.route_id ?? ''],
                    ],
                  ],
                },
                {
                  id: 'stops-highlight',
                  source: 'sample',
                  'source-layer': 'stopsoutput', // Name of the geojson file when converting to pmtile. stops-output.geojson -> stopssoutput
                  type: 'circle',
                  paint: {
                    'circle-radius': 7,
                    'circle-color': generateStopColorExpression(
                      routeIdToColorMap,
                    ) as ExpressionSpecification, // VERY IMPORTANT: during the conversion to PMTiles, the route_colors are stored as strings with quotes NOT arrays. [1,2,3] -> "["1","2","3"]"
                    'circle-opacity': 1,
                  },
                  minzoom: 10,
                  maxzoom: 22,
                  filter: hideStops
                    ? !hideStops
                    : [
                        'any',
                        ['in', ['get', 'stop_id'], ['literal', hoverInfo]],
                        [
                          'in',
                          ['get', 'stop_id'],
                          ['literal', mapClickStopData?.stop_id ?? ''],
                        ],
                        [
                          'any',
                          ...filteredRoutes.map((id) => {
                            return [
                              'in',
                              `\"${id}\"`,
                              ['get', 'route_ids'],
                            ] as any; // VERY IMPORTANT: during the conversion to PMTiles, the route_ids are stored as strings with quotes NOT arrays. [1,2,3] -> "["1","2","3"]"
                          }),
                        ],
                        [
                          'any',
                          ...hoverInfo.map((id) => {
                            return [
                              'in',
                              `\"${id}\"`,
                              ['get', 'route_ids'],
                            ] as any;
                          }),
                        ],
                      ],
                },
                {
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
                            ] as any; // VERY IMPORTANT: during the conversion to PMTiles, the route_ids are stored as strings with quotes NOT arrays. [1,2,3] -> "["1","2","3"]"
                          }),
                        ],
                        [
                          'any',
                          ...hoverInfo.map((id) => {
                            return [
                              'in',
                              `\"${id}\"`,
                              ['get', 'route_ids'],
                            ] as any;
                          }),
                        ],
                      ],
                },
              ],
            }}
          >
            {/* TODO: Idea only display the compass and scale on advanced map view */}
            <ScaleControl position='bottom-left' unit='metric' />
            <NavigationControl
              position='top-right'
              showCompass={true}
              showZoom={true}
              style={{
                backgroundColor: 'white',
                marginTop: '72px',
                marginRight: '15px',
                boxShadow:
                  'rgba(0, 0, 0, 0.2) 0px 3px 5px -1px, rgba(0, 0, 0, 0.14) 0px 6px 10px 0px, rgba(0, 0, 0, 0.12) 0px 1px 18px 0px',
              }}
            />
            <MapDataPopup
              mapClickRouteData={mapClickRouteData}
              mapClickStopData={mapClickStopData}
              onPopupClose={handlePopupClose}
            ></MapDataPopup>
          </Map>
        </Box>
      </Box>
    </MapProvider>
  );
};
