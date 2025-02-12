/* eslint-disable */

import { useEffect, useRef, useState } from 'react';
import Map, { type MapRef, MapProvider } from 'react-map-gl/maplibre';
import maplibregl, { type LngLatBoundsLike } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Protocol } from 'pmtiles';
import { type LatLngExpression } from 'leaflet';
import type { FeatureCollection } from 'geojson';
import { MapElement } from './MapElement';
import { Box } from '@mui/material';

export interface MapProps {
  polygon: LatLngExpression[];
}

export const Map2 = (props: React.PropsWithChildren<MapProps>): JSX.Element => {
  const [hoverInfo, setHoverInfo] = useState<string>('');
  const [hoverData, setHoverData] = useState<string>('');
  const [mapElement, setMapElement] = useState<MapElement[]>([]);
  const mapRef = useRef<MapRef>(null);

  const handleMouseMove = (event: maplibregl.MapLayerMouseEvent): void => {
    // Ensure that the mapRef is not null before trying to access the map
    const map = mapRef.current?.getMap();
    const mapElements: MapElement[] = [];

    if (map != undefined) {
      // Get the features under the mouse pointer
      const features = map.queryRenderedFeatures(event.point, {
        layers: ['stops', 'routes'], // Change this to your actual layer ID
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

        const feature = features[0]; // assuming you are dealing with one feature at a time
        // setHoverInfo({
        //   coordinates: feature.geometry.coordinates,
        //   properties: feature.properties,
        // });
        if (feature.properties.route_id != undefined) {
          //console.log("ROUTE DATA: ", feature.properties); // route_type 1 = metro, 3 = bus
          setHoverInfo(feature.properties.route_id);
          setHoverData(feature.properties.route_long_name);
        } else {
          setHoverInfo(feature.properties.stop_id);
          setHoverData(feature.properties.stop_name);
        }
      } else {
        setHoverInfo('');
        setHoverData('');
        setMapElement([]);
      }
    }
  };
  ///

  useEffect(() => {
    // Will be called on add statup only once
    const protocol = new Protocol();
    maplibregl.addProtocol('pmtiles', protocol.tile);
    return () => {
      maplibregl.removeProtocol('pmtiles');
    };
  }, []);

  const getBoundsFromCoordinates = (
    coordinates: [number, number][],
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
    props.polygon as [number, number][],
  );

  // in polygon: IMPORTANT - the coordinates are in the format [lat, lng] (not [lng, lat])
  const boundingBoxFormmated = props.polygon.map((point: any) => [
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

  console.log();

  return (
    <MapProvider>
      <Box sx={{ width: '100%', height: '100%', position: 'relative' }}>
        <MapElement mapElements={mapElement}></MapElement>
        <Map
          onClick={handleMouseMove}
          ref={mapRef}
          onMouseMove={(event) => handleMouseMove(event)}
          style={{ width: '100%', height: '100%' }}
          initialViewState={{ bounds }}
          interactiveLayerIds={['stops', 'routes']}
          scrollZoom={true}
          dragPan={true}
          mapStyle={{
            version: 8,
            sources: {
              'raster-tiles': {
                type: 'raster',
                tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
                tileSize: 256,
                attribution:
                  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
              },
              sample: {
                type: 'vector',
                url: 'pmtiles://https://storage.googleapis.com/map-details-bucket-test/stops.pmtiles', // Google Storage Bucket (CORS enabled)
              },
              routes: {
                type: 'vector',
                url: 'pmtiles://https://storage.googleapis.com/map-details-bucket-test/routes.pmtiles', // Google Storage Bucket (CORS enabled)
              },
              // boundingBox: {
              //   type: 'geojson',
              //   data: geojson, // displays the bounding box
              // },
            },
            // Order matters: the last layer will be on top
            layers: [
              {
                id: 'simple-tiles',
                type: 'raster',
                source: 'raster-tiles',
                minzoom: 0,
                maxzoom: 22,
              },

              {
                id: 'routes-white',
                source: 'routes',
                'source-layer': 'output', // Name in the
                type: 'line',
                paint: {
                  // style and color of the stops
                  'line-color': '#ffffff',
                  'line-width': [
                    'match',
                    ['get', 'route_type'], // Property from the vector tile
                    '3',
                    3, // 3 = bus
                    '1',
                    8, // 1 = metro
                    3, // Default width
                  ],
                },
              },
              {
                id: 'routes',
                source: 'routes',
                'source-layer': 'output', // Name in the
                type: 'line',
                paint: {
                  // style and color of the stops
                  'line-color': ['concat', '#', ['get', 'route_color']],
                  'line-width': [
                    'match',
                    ['get', 'route_type'], // Property from the vector tile
                    '3',
                    1, // 3 = bus
                    '1',
                    4, // 1 = metro
                    3, // Default width
                  ],
                },
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
                source: 'sample',
                'source-layer': 'stops', // Name in the
                type: 'circle',
                paint: {
                  // style and color of the stops
                  'circle-radius': 3,
                  'circle-color': '#000000',
                },
                minzoom: 12,
                maxzoom: 22,
              },
              {
                id: 'routes-highlight',
                source: 'routes',
                'source-layer': 'output', // Name in the
                type: 'line',
                paint: {
                  // style and color of the stops
                  'line-color': ['concat', '#', ['get', 'route_color']],
                  'line-width': [
                    'match',
                    ['get', 'route_type'], // Property from the vector tile
                    '3',
                    4, // 3 = bus
                    '1',
                    6, // 1 = metro
                    3, // Default width
                  ],
                },
                minzoom: 10,
                maxzoom: 22,
                filter: ['==', ['get', 'route_id'], hoverInfo],
              },
              {
                id: 'stops-highlight',
                source: 'sample',
                'source-layer': 'stops',
                type: 'circle',
                paint: {
                  'circle-radius': 8, // Make it larger
                  'circle-color': '#ff0000', // Red highlight
                  'circle-opacity': 0.8,
                },
                filter: ['==', ['get', 'stop_id'], hoverInfo], // Apply only to hovered feature
              },
            ],
          }}
        ></Map>
      </Box>
    </MapProvider>
  );
};
