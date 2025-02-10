/* eslint-disable */

import { useEffect, useRef, useState } from 'react';
import Map, { type MapRef, MapProvider } from 'react-map-gl/maplibre';
import maplibregl, { type LngLatBoundsLike } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Protocol } from 'pmtiles';
import { type LatLngExpression } from 'leaflet';
import type { FeatureCollection } from 'geojson';

export interface MapProps {
  polygon: LatLngExpression[];
}

export const Map2 = (props: React.PropsWithChildren<MapProps>): JSX.Element => {
  const [hoverInfo, setHoverInfo] = useState<string>('');
  const [hoverData, setHoverData] = useState<string>('');
  const mapRef = useRef<MapRef>(null);

  const handleMouseMove = (event: maplibregl.MapLayerMouseEvent): void => {
    // Ensure that the mapRef is not null before trying to access the map
    const map = mapRef.current?.getMap();

    if (map != undefined) {
      // Get the features under the mouse pointer
      const features = map.queryRenderedFeatures(event.point, {
        layers: ['stops'], // Change this to your actual layer ID
      });

      if (features.length > 0) {
        const feature = features[0]; // assuming you are dealing with one feature at a time
        // setHoverInfo({
        //   coordinates: feature.geometry.coordinates,
        //   properties: feature.properties,
        // });
        setHoverInfo(feature.properties.stop_id);
        setHoverData(feature.properties.stop_name);
      } else {
        setHoverInfo('');
        setHoverData('');
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
      <Map
        onClick={handleMouseMove}
        ref={mapRef}
        onMouseMove={(event) => handleMouseMove(event)}
        style={{ width: '100%', height: '100%' }}
        initialViewState={{ bounds }}
        interactiveLayerIds={['stops']}

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
            boundingBox: {
              type: 'geojson',
              data: geojson, // displays the bounding box
            },
          },
          layers: [
            {
              id: 'simple-tiles',
              type: 'raster',
              source: 'raster-tiles',
              minzoom: 0,
              maxzoom: 22,
            },
            {
              id: 'stops',
              source: 'sample',
              'source-layer': 'stops', // Name in the
              type: 'circle',
              paint: {
                // style and color of the stops
                'circle-radius': 5,
                'circle-color': '#088',
              },
              minzoom: 10,
              maxzoom: 22,
            },
            {
              id: 'boundingBox',
              type: 'fill',
              source: 'boundingBox',
              paint: {
                'fill-color': '#088',
                'fill-opacity': 0.8,
              },
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
      <h1>Stop Name: {hoverData}</h1>
    </MapProvider>
  );
};
