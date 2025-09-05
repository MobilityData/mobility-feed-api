import TramIcon from '@mui/icons-material/Tram';
import SubwayIcon from '@mui/icons-material/Subway';
import TrainIcon from '@mui/icons-material/Train';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import DirectionsBoatIcon from '@mui/icons-material/DirectionsBoat';
import CableIcon from '@mui/icons-material/Cable';
import EmojiTransportationIcon from '@mui/icons-material/EmojiTransportation'; // for Gondola
import TerrainIcon from '@mui/icons-material/Terrain'; // for Funicular
import DepartureBoardIcon from '@mui/icons-material/DepartureBoard'; // for Monorail
import SpeedIcon from '@mui/icons-material/Speed'; // for High Speed Train
import FlightIcon from '@mui/icons-material/Flight';
import MeetingRoomIcon from '@mui/icons-material/MeetingRoom';
import PlaceIcon from '@mui/icons-material/Place';
import DirectionsSubwayIcon from '@mui/icons-material/DirectionsSubway';
import type { SvgIconComponent } from '@mui/icons-material';
import type { TFunction } from 'i18next';

export interface RouteTypeMetadata {
  name: string;
  icon: SvgIconComponent;
  isDefault?: boolean;
}

export const defaultRouteType: RouteTypeMetadata = {
  name: '',
  icon: PlaceIcon,
  isDefault: true,
};

export const routeTypesMapping: Record<string, RouteTypeMetadata> = {
  '0': { name: 'Tram', icon: TramIcon },
  '1': { name: 'Subway', icon: SubwayIcon },
  '2': { name: 'Rail', icon: TrainIcon },
  '3': { name: 'Bus', icon: DirectionsBusIcon },
  '4': { name: 'Ferry', icon: DirectionsBoatIcon },
  '5': { name: 'Cable Car', icon: CableIcon },
  '6': { name: 'Gondola', icon: EmojiTransportationIcon },
  '7': { name: 'Funicular', icon: TerrainIcon },
  '11': { name: 'Monorail', icon: DepartureBoardIcon },
  '12': { name: 'High Speed Train', icon: SpeedIcon },
  '13': { name: 'Airplane', icon: FlightIcon },
};

// TODO: find better icons for these
export const locationTypesMapping: Record<string, RouteTypeMetadata> = {
  '0': { name: 'Stop', icon: DirectionsBusIcon },
  '1': { name: 'Station', icon: TrainIcon },
  '2': { name: 'Entrance/Exit', icon: MeetingRoomIcon },
  '3': { name: 'Generic Node', icon: PlaceIcon },
  '4': { name: 'Boarding Area', icon: DirectionsSubwayIcon },
};
export const reversedRouteTypesMapping = Object.fromEntries(
  Object.entries(routeTypesMapping).map(([k, v]) => [v.name, k]),
);

export const getRouteByTypeOrDefault = (
  routeType: string | undefined | null,
): RouteTypeMetadata => {
  if (routeType == null) {
    return defaultRouteType;
  }
  return routeTypesMapping[routeType] ?? defaultRouteType;
};

export const getRouteTypeTranslatedName = (
  routeTypeId: string,
  t: TFunction,
): string => {
  const routeType = getRouteByTypeOrDefault(routeTypeId);
  return !(routeType.isDefault ?? false)
    ? t(`common:gtfsSpec.routeType.${routeTypeId}.name`)
    : '';
};
