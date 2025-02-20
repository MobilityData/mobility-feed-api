import * as React from 'react';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import { type LatLngBoundsExpression, type LatLngExpression } from 'leaflet';
import { PopupTable } from './PopupTable';
import { createRoot } from 'react-dom/client';

export interface MapProps {
  geoJSONData: any;
  polygon: LatLngExpression[];
}

export const MapGeoJSON = (
  props: React.PropsWithChildren<MapProps>,
): JSX.Element => {
  return (
    <MapContainer
      bounds={props.polygon as LatLngBoundsExpression}
      zoom={8}
      style={{ minHeight: '400px', height: '100%' }}
      data-testid='geojson-map'
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
      />

      {props.geoJSONData !== null && (
        <GeoJSON
          data={props.geoJSONData}
          onEachFeature={(feature, layer) => {
            const container = document.createElement('div');
            const root = createRoot(container);
            root.render(<PopupTable properties={feature.properties} />);
            layer.bindPopup(container);
          }}
          style={(feature) => ({
            weight: 3,
            opacity: 1,
            color: feature?.properties?.color ?? '#3388ff',
            fillOpacity: 0.3,
          })}
        />
      )}
    </MapContainer>
  );
};
