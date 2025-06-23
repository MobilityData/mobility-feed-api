/* eslint-disable */

import { useEffect, useRef, useState } from 'react';
import Map, {
  type MapRef,
  MapProvider,
  NavigationControl,
  ScaleControl,
  Popup,
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
import { MapElement } from './MapElement';
import { routeTypesMapping } from "../constants/RouteTypes";

export interface GtfsVisualizationMapProps {
  polygon: LatLngExpression[];
  filteredRoutes?: string[];
  filteredRouteTypes?: string[];
  hideStops?: boolean;
}

export const GtfsVisualizationMap = ({
  polygon,
  filteredRoutes = [],
  filteredRouteTypes = [],
  hideStops = false,
}: GtfsVisualizationMapProps): JSX.Element => {
  const theme = useTheme();
  const [hoverInfo, setHoverInfo] = useState<string[]>([]);
  const [hoverData, setHoverData] = useState<string>('');
  const [mapElement, setMapElement] = useState<MapElement[]>([]);
  const [mapClickData, setMapClickData] = useState<
    Record<string, string | number>
  >({});
  const [anchorPosition, setAnchorPosition] = useState<{
    left: number;
    top: number;
  } | null>(null);
  const mapRef = useRef<MapRef>(null);

  const reversedRouteTypesMapping = Object.fromEntries(
    Object.entries(routeTypesMapping).map(([k, v]) => [v, k])
  );
  const filteredRouteTypesIds = filteredRouteTypes.map(d => reversedRouteTypesMapping[d]);

  // Create a map to store routeId to routeColor mapping
  const routeIdToColorMap: Record<string, string> = {};
  mapElement.forEach((el) => {
    if (!el.isStop && el.routeId && el.routeColor) {
      routeIdToColorMap[el.routeId] = el.routeColor;
    }
  });
  function generateStopColorExpression(
    routeIdToColor: Record<string, string>,
    fallback = '#888'
  ): ExpressionSpecification {
    const expression: any[] = ['case'];

    Object.entries(routeIdToColor).forEach(([routeId, color]) => {
      expression.push(
        ['in', `"${routeId}"`, ['get', 'route_ids']],
        `#${color}`
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
      const { offsetLeft, offsetTop } = mapRef.current!.getContainer();
      const features = map.queryRenderedFeatures(event.point, {
        layers: ['stops', 'routes'], // Change this to your actual layer ID
      });
      setMapClickData({
        ...(features[0]?.properties || {}),
        longitude: event.lngLat.lng,
        latitude: event.lngLat.lat,
      }); // Example properties, adjust as needed
      console.log('Mouse clicked on map:', features);
      setAnchorPosition({
        left: event.point.x + offsetLeft,
        top: event.point.y + offsetTop,
      });
    }
  };

  const handleClose = () => {
    setMapClickData({});
    setAnchorPosition(null);
  };

  //console.log('this is it mapClickData', mapClickData);

  const handleMouseMove = (event: maplibregl.MapLayerMouseEvent): void => {
    // Ensure that the mapRef is not null before trying to access the map
    const map = mapRef.current?.getMap();
    const mapElements: MapElement[] = [];

    if (map != undefined) {
      // Get the features under the mouse pointer
      const features = map.queryRenderedFeatures(event.point, {
        layers: ['stops', 'routes', 'routes-white'], // Change this to your actual layer ID
      });

      if (features.length > 0) {
        features.forEach((feature) => {
          if (feature.layer.id === 'stops') {
            const mapElement: MapElement = {
              isStop: true,
              name: feature.properties.stop_name,
            };
            mapElements.push(mapElement);
          } else {
            const mapElement: MapElement = {
              isStop: false,
              name: feature.properties.route_long_name,
              routeType: feature.properties.route_type,
              routeColor: feature.properties.route_color,
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
            // border: '2px solid',
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
            interactiveLayerIds={['stops', 'routes', 'routes-white']}
            scrollZoom={true}
            dragPan={true}
            // https://pmtiles.io/ Good tool for debugging PMTiles
            mapStyle={{
              version: 8,
              sources: {
                'raster-tiles': {
                  type: 'raster',
                  tiles: [
                    'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
                  ],
                  tileSize: 256,
                  attribution:
                    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                },
                sample: {
                  type: 'vector',
                  //url: 'pmtiles://https://storage.googleapis.com/map-details-bucket-test/stops-v2.pmtiles', // Google Storage Bucket (CORS enabled)
                  url: 'pmtiles://https://storage.googleapis.com/map-details-bucket-test/stops-bordeaux.pmtiles', // bordeaux
                },
                routes: {
                  type: 'vector',
                  //url: 'pmtiles://https://storage.googleapis.com/map-details-bucket-test/routes-v2.pmtiles', // (STM) Google Storage Bucket (CORS enabled)
                  url: 'pmtiles://https://storage.googleapis.com/map-details-bucket-test/routes-bordeaux.pmtiles', // bordeaux
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
                    'line-color': '#ffffff',
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
                    'line-opacity': [ // Opacity based on whether the route is selected or not
                      'case',
                      ['any', ['==', filteredRoutes.length, 0], ['in', ['get', 'route_id'], ['literal', filteredRoutes]]],
                      0.4, // default opacity if selected or no filter
                      0.1, // faded if NOT in filteredRoutes
                    ]
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
                  ],
                },
                {
                  id: 'stops-highlight',
                  source: 'sample',
                  'source-layer': 'stopsoutput', // Name of the geojson file when converting to pmtile. stops-output.geojson -> stopssoutput
                  type: 'circle',
                  paint: {
                    'circle-radius': 6,
                    'circle-color': generateStopColorExpression(routeIdToColorMap) as ExpressionSpecification, // VERY IMPORTANT: during the conversion to PMTiles, the route_colors are stored as strings with quotes NOT arrays. [1,2,3] -> "["1","2","3"]"
                    'circle-opacity': 0.8,
                  },
                  minzoom: 10,
                  maxzoom: 22,
                  filter: hideStops ? !hideStops : [
                    'any',
                    ['in', ['get', 'stop_id'], ['literal', hoverInfo]],
                    [
                      'any',
                      ...filteredRoutes.map((id) => {
                        return ['in', `\"${id}\"`, ['get', 'route_ids']] as any; // VERY IMPORTANT: during the conversion to PMTiles, the route_ids are stored as strings with quotes NOT arrays. [1,2,3] -> "["1","2","3"]"
                      }),
                    ],
                    [
                      'any',
                      ...hoverInfo.map((id) => {
                        return ['in', `\"${id}\"`, ['get', 'route_ids']] as any;
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
                    'circle-color': '#ffffff',
                    'circle-opacity': 1,
                  },
                  filter: hideStops ? !hideStops : [
                    'any',
                    ['in', ['get', 'stop_id'], ['literal', hoverInfo]],
                    [
                      'any',
                      ...filteredRoutes.map((id) => {
                        return ['in', `\"${id}\"`, ['get', 'route_ids']] as any; // VERY IMPORTANT: during the conversion to PMTiles, the route_ids are stored as strings with quotes NOT arrays. [1,2,3] -> "["1","2","3"]"
                      }),
                    ],
                    [
                      'any',
                      ...hoverInfo.map((id) => {
                        return ['in', `\"${id}\"`, ['get', 'route_ids']] as any;
                      }),
                    ],
                  ],
                }
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

            {/*TODO: could be own component*/}
            {Object.keys(mapClickData).length > 0 && (
              <Popup
                longitude={Number(mapClickData.longitude)}
                latitude={Number(mapClickData.latitude)}
                anchor='top'
                onClose={() => setMapClickData({})}
                closeOnClick={false}
              >
                <div>
                  <strong>Clicked at:</strong>
                  <br />
                  {Number(mapClickData.latitude).toFixed(5)},{' '}
                  {Number(mapClickData.longitude).toFixed(5)}
                  <br />
                  {Object.entries(mapClickData).map(([key, value]) => (
                    <p>
                      {key} - {value}
                    </p>
                  ))}
                </div>
              </Popup>
            )}
          </Map>
        </Box>
      </Box>
    </MapProvider>
  );
};
