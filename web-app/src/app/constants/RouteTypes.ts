export const routeTypesMapping: Record<string, string> = {
  '0': 'Tram',
  '1': 'Subway',
  '2': 'Rail',
  '3': 'Bus',
  '4': 'Ferry',
  '5': 'Cable Car',
  '6': 'Gondola',
  '7': 'Funicular',
  '11': 'Monorail',
  '12': 'High Speed Train',
  '13': 'Airplane',
};

export const reversedRouteTypesMapping = Object.fromEntries(
  Object.entries(routeTypesMapping).map(([k, v]) => [v, k]),
);
