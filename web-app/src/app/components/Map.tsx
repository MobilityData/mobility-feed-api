import * as React from 'react';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, Polygon } from 'react-leaflet';
import { type LatLngBoundsExpression, type LatLngExpression } from 'leaflet';

export interface MapProps {
  polygon: LatLngExpression[];
}

export const Map = (props: React.PropsWithChildren<MapProps>): JSX.Element => {
  return (
    <MapContainer
      bounds={props.polygon as LatLngBoundsExpression}
      zoom={8}
      style={{ minHeight: '400px', height: '100%' }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
      />
      <Polygon positions={props.polygon}></Polygon>
    </MapContainer>
  );
};
