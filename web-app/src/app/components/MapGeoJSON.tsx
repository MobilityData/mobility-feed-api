import * as React from 'react';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import { type LatLngBoundsExpression } from 'leaflet';

export interface MapProps {
  latest_dataset_url: string; // The base URL to construct the GeoJSON file path
}

export const MapGeoJSON = (
  props: React.PropsWithChildren<MapProps>,
): JSX.Element => {
  const [geoJsonData, setGeoJsonData] = React.useState(null);

  // Construct the GeoJSON URL based on the latest_dataset_url
  const geoJsonUrl = props.latest_dataset_url
    .split('/')
    .slice(0, -2)
    .concat('geolocation.geojson')
    .join('/');
  console.log('geoJsonUrl = ', geoJsonUrl);

  React.useEffect(() => {
    const fetchGeoJson = async (): Promise<void> => {
      try {
        const response = await fetch(geoJsonUrl);
        if (!response.ok) {
          throw new Error(`Failed to fetch GeoJSON: ${response.statusText}`);
        }
        const data = await response.json();
        setGeoJsonData(data);
      } catch (error) {
        console.error(error);
      }
    };

    fetchGeoJson().then(
      () => {
        console.log('GeoJSON fetched successfully');
      },
      (error) => {
        console.error('Failed to fetch GeoJSON: ', error);
      },
    );
  }, [geoJsonUrl]);

  const getBoundsFromGeoJson = (
    geoJson: any,
  ): LatLngBoundsExpression | undefined => {
    if (!geoJson?.features) return undefined;

    const coordinates = geoJson.features.flatMap((feature: any) =>
      feature.geometry.coordinates.flat(),
    );
    const lats = coordinates.map((coord: [number, number]) => coord[1]);
    const lngs = coordinates.map((coord: [number, number]) => coord[0]);

    const southWest = [Math.min(...lats), Math.min(...lngs)] as [
      number,
      number,
    ];
    const northEast = [Math.max(...lats), Math.max(...lngs)] as [
      number,
      number,
    ];
    return [southWest, northEast] as LatLngBoundsExpression;
  };

  const bounds = geoJsonData ? getBoundsFromGeoJson(geoJsonData) : undefined;

  return (
    <MapContainer
      bounds={bounds}
      zoom={8}
      style={{ minHeight: '400px', height: '100%' }}
      data-testid='geojson-map'
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
      />
      {geoJsonData && (
        <GeoJSON
          data={geoJsonData}
          style={(feature) => ({
            fillColor: feature?.properties.color || '#3388ff', // Default to blue if no color is specified
            weight: 2,
            opacity: 1,
            color: 'black', // Border color
            fillOpacity: 0.7,
          })}
        />
      )}
    </MapContainer>
  );
};
