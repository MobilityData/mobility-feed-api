import * as React from 'react';
import 'leaflet/dist/leaflet.css';
import { MapContainer, TileLayer, Polygon } from 'react-leaflet';
import { type LatLngBoundsExpression, type LatLngExpression } from 'leaflet';
import { useTheme } from '@mui/material/styles';
import { ThemeModeEnum } from '../Theme';

export interface MapProps {
  polygon: LatLngExpression[];
}

export const Map = (props: React.PropsWithChildren<MapProps>): JSX.Element => {
  const theme = useTheme();
  const mapTiles =
    theme.palette.mode === ThemeModeEnum.dark
      ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
      : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
  return (
    <>
      <MapContainer
      bounds={props.polygon as LatLngBoundsExpression}
      zoom={8}
      style={{ minHeight: '400px', height: '100%' }}
      data-testid='bounding-box-map'
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; CartoDB'
        url={mapTiles}
      />
      <Polygon positions={props.polygon}></Polygon>
    </MapContainer>
      {/* <Map2 polygon={props.polygon}></Map2> */}
    </>
  );
};
