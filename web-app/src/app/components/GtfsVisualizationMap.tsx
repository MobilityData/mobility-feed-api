import { useEffect, useMemo, useRef, useState } from 'react';
import Map, {
  MapProvider,
  type MapRef,
  NavigationControl,
  ScaleControl,
} from 'react-map-gl/maplibre';
import maplibregl, { type LngLatBoundsLike } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Protocol } from 'pmtiles';
import { type LatLngExpression } from 'leaflet';
import { Box, useTheme } from '@mui/material';

import {
  MapElement,
  type MapRouteElement,
  type MapStopElement,
  type MapElementType,
} from './MapElement';
import { MapDataPopup } from './Map/MapDataPopup';
import type { GtfsRoute } from '../types';
import { createPrecomputation, extendBBoxes } from '../utils/precompute';
import { SelectedRoutesStopsPanel } from './Map/SelectedRoutesStopsPanel';
import { ScanningOverlay } from './Map/ScanningOverlay';
import {
  extractRouteIds,
  getBoundsFromCoordinates,
} from './GtfsVisualizationMap.functions';
import {
  RouteHighlightLayer,
  RouteLayer,
  RoutesWhiteLayer,
  StopLayer,
  StopsHighlightLayer,
  StopsHighlightOuterLayer,
  StopsIndexLayer,
} from './GtfsVisualizationMap.layers';

interface LatestDatasetLite {
  hosted_url?: string;
  id?: string;
  stable_id?: string;
}

export interface GtfsVisualizationMapProps {
  polygon: LatLngExpression[];
  latestDataset?: LatestDatasetLite;
  filteredRoutes?: string[];
  filteredRouteTypeIds?: string[];
  hideStops?: boolean;
  dataDisplayLimit?: number;
  routes?: GtfsRoute[];
  refocusTrigger?: boolean;
  stopRadius?: number;
  /** If true, skip precomputation + scanning overlay + auto-fit-on-idle */
  preview?: boolean;
}

export const GtfsVisualizationMap = ({
  polygon,
  latestDataset,
  filteredRoutes = [],
  filteredRouteTypeIds = [],
  hideStops = false,
  dataDisplayLimit = 10,
  routes = [],
  refocusTrigger = false,
  stopRadius = 3,
  preview = true,
}: GtfsVisualizationMapProps): JSX.Element => {
  const theme = useTheme();
  const [hoverInfo, setHoverInfo] = useState<string[]>([]);
  const [mapElements, setMapElements] = useState<MapElementType[]>([]);
  const [mapClickRouteData, setMapClickRouteData] = useState<Record<
    string,
    string
  > | null>(null);
  const [mapClickStopData, setMapClickStopData] = useState<Record<
    string,
    string
  > | null>(null);
  // Stable list of all stops matched to selected routes (independent of hover)
  const [selectedRouteStops, setSelectedRouteStops] = useState<
    MapStopElement[]
  >([]);
  // Scanning overlay state
  const [isScanning, setIsScanning] = useState(false);
  const [scannedTiles, setScannedTiles] = useState(0);
  const [totalTiles, setTotalTiles] = useState(0);
  const [scanRowsCols, setScanRowsCols] = useState<{
    rows: number;
    cols: number;
  } | null>(null);
  // Selected stop id from the panel (for cute highlight)
  const [selectedStopId, setSelectedStopId] = useState<string | null>(null);
  const { stopsPmtilesUrl, routesPmtilesUrl } = useMemo(() => {
    const baseUrl =
      latestDataset?.hosted_url != null
        ? latestDataset.hosted_url.replace(/[^/]+$/, '')
        : undefined;
    const stops = `${baseUrl}/pmtiles/stops.pmtiles`;
    const routes = `${baseUrl}/pmtiles/routes.pmtiles`;
    return { stopsPmtilesUrl: stops, routesPmtilesUrl: routes };
  }, [latestDataset?.id, latestDataset?.stable_id]);

  const mapRef = useRef<MapRef>(null);
  const didInitRef = useRef(false);

  // Build routeId -> color map from the currently shown hover/click panels
  const routeIdToColorMap: Record<string, string> = {};
  mapElements.forEach((el) => {
    if (!el.isStop) {
      const routeElement: MapRouteElement = el as MapRouteElement;
      if (
        routeElement?.routeId != null &&
        routeElement.routeId !== '' &&
        routeElement.routeColor != null &&
        routeElement.routeColor !== ''
      ) {
        routeIdToColorMap[routeElement.routeId] = routeElement.routeColor;
      }
    }
  });
  // Pull colors for the currently filtered route IDs (from props.routes)
  const filteredRouteColors: Record<string, string> = useMemo(() => {
    const m: Record<string, string> = {};
    for (const rid of filteredRoutes) {
      const r = (routes ?? []).find((rr) => String(rr.routeId) === String(rid));
      // strip leading '#' because generateStopColorExpression expects raw hex
      if (r?.color != null && r.color !== '')
        m[String(rid)] = String(r.color).replace(/^#/, '');
    }
    return m;
  }, [filteredRoutes, routes]);

  // Merge: filtered-route colors (take priority) + hover/click colors
  const stopHighlightColorMap: Record<string, string> = {
    ...routeIdToColorMap,
    ...filteredRouteColors,
  };

  const handleMouseClick = (event: maplibregl.MapLayerMouseEvent): void => {
    const map = mapRef.current?.getMap();
    if (map != undefined) {
      // Get the features under the mouse pointer
      const features = map.queryRenderedFeatures(event.point, {
        layers: ['stops-index', 'routes-highlight'],
      });
      const selectedStop = features.find(
        (feature) => feature.layer.id === 'stops-index',
      );
      if (selectedStop != undefined) {
        setMapClickStopData({
          ...selectedStop.properties,
          longitude: String(event.lngLat.lng),
          latitude: String(event.lngLat.lat),
        });
        setSelectedStopId(String(selectedStop.properties?.stop_id ?? null));
        setMapClickRouteData(null);
        return;
      }

      const selectedRoute = features.find(
        (f) => f.layer.id === 'routes-highlight',
      );
      if (selectedRoute != undefined) {
        setMapClickRouteData({
          ...selectedRoute.properties,
          longitude: String(event.lngLat.lng),
          latitude: String(event.lngLat.lat),
        });
        setMapClickStopData(null);
      }
    }
  };

  const handlePopupClose = (): void => {
    setMapClickRouteData(null);
    setMapClickStopData(null);
    setSelectedStopId(null);
  };

  const handleMouseMove = (event: maplibregl.MapLayerMouseEvent): void => {
    const map = mapRef.current?.getMap();
    const next: MapElementType[] = [];
    if (map != undefined) {
      const features = map.queryRenderedFeatures(event.point, {
        layers: ['stops', 'routes', 'routes-white'],
      });

      if (
        features.length > 0 ||
        mapClickRouteData != null ||
        mapClickStopData != null
      ) {
        if (mapClickRouteData != null) {
          const routeData: MapRouteElement = {
            isStop: false,
            name: mapClickRouteData.route_long_name,
            routeType: Number(mapClickRouteData.route_type),
            routeColor: mapClickRouteData.route_color,
            routeTextColor: mapClickRouteData.route_text_color,
            routeId: mapClickRouteData.route_id,
          };
          next.push(routeData);
        }
        if (mapClickStopData != null) {
          const stopData: MapStopElement = {
            isStop: true,
            name: mapClickStopData.stop_name,
            locationType: Number(mapClickStopData.location_type),
            stopId: mapClickStopData.stop_id,
            stopLat: Number(mapClickStopData.latitude),
            stopLon: Number(mapClickStopData.longitude),
          };
          next.push(stopData);
        }
        features.forEach((feature) => {
          if (feature.layer.id === 'stops') {
            const stopData: MapStopElement = {
              isStop: true,
              name: feature.properties.stop_name,
              locationType: Number(feature.properties.location_type),
              stopId: feature.properties.stop_id,
              stopLat: Number(feature.properties.stop_lat),
              stopLon: Number(feature.properties.stop_lon),
            };
            next.push(stopData);
          } else {
            const routeData: MapRouteElement = {
              isStop: false,
              name: feature.properties.route_long_name,
              routeType: feature.properties.route_type,
              routeColor: feature.properties.route_color,
              routeTextColor: feature.properties.route_text_color,
              routeId: feature.properties.route_id,
            };
            next.push(routeData);
          }
        });

        setMapElements(next);

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
        setMapElements([]);
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

  const bounds: LngLatBoundsLike = getBoundsFromCoordinates(
    polygon as Array<[number, number]>,
  );

  // route IDs coming from selected route types
  const routeIdsFromTypes =
    filteredRouteTypeIds.length > 0
      ? (routes ?? [])
          .filter((r) => filteredRouteTypeIds.includes(String(r.routeType)))
          .map((r) => String(r.routeId))
      : [];

  // union of explicit route IDs + those implied by selected types
  const allSelectedRouteIds = [...filteredRoutes, ...routeIdsFromTypes];

  // --- SELECTED ROUTE STOPS PANEL ---
  useEffect(() => {
    // If no route-id filter, clear and exit
    if (filteredRoutes.length === 0) {
      setSelectedRouteStops([]);
      return;
    }

    // If we have precomputed data, use it and bail
    if (precomputedReadyRef.current) {
      const seen = new Set<string>();
      const out: MapStopElement[] = [];
      for (const rid of filteredRoutes) {
        const list = stopsByRouteIdRef.current[rid] ?? [];
        for (const s of list) {
          if (seen.has(s.stopId)) continue;
          seen.add(s.stopId);
          out.push(s);
        }
      }
      out.sort((a, b) =>
        a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }),
      );
      setSelectedRouteStops(out);
    }
  }, [filteredRoutes]);

  // --- PRECOMPUTED INDEXES ---
  const precomputedReadyRef = useRef(false);
  const routeIdToBBoxRef = useRef<Record<string, LngLatBoundsLike>>({}); // Map routeId -> bbox of all stops on that route
  const routeTypeToBBoxRef = useRef<Record<string, LngLatBoundsLike>>({}); // Map routeType -> bbox of all stops on routes of that type
  const stopsByRouteIdRef = useRef<Record<string, MapStopElement[]>>({}); // Map routeId -> all stops on that route

  // Map routeId -> routeType from props.routes
  const routeIdToType = useMemo(() => {
    const m: Record<string, string> = {};
    for (const r of routes) {
      if (r?.routeId != null && r?.routeType != null) {
        m[String(r.routeId)] = String(r.routeType);
      }
    }
    return m;
  }, [routes]);

  // --- instantiate the extracted precomputation with identical behavior ---
  const cancelRequestRef = useRef<boolean>(false);
  const precomp = useMemo(
    () =>
      createPrecomputation({
        mapRef,
        bounds,
        preview,
        extractRouteIds,
        setIsScanning,
        setScanRowsCols,
        setScannedTiles,
        setTotalTiles,
        routeIdToBBoxRef,
        routeTypeToBBoxRef,
        stopsByRouteIdRef,
        precomputedReadyRef,
        routeIdToType,
        cancelRequestRef,
      }),
    [
      mapRef,
      bounds,
      preview,
      routeIdToType,
      // setters and refs are stable enough in React; include for completeness
      setIsScanning,
      setScanRowsCols,
      setScannedTiles,
      setTotalTiles,
    ],
  );

  // Helper to focus & stick a stop from the panel
  const focusStopFromPanel = async (s: MapStopElement): Promise<void> => {
    const map = mapRef.current?.getMap();
    if (map == null) return;

    // 1) Move the camera
    map.easeTo({
      center: [s.stopLon, s.stopLat],
      zoom: Math.max(map.getZoom(), 13),
      duration: 400,
    });

    // 2) Wait for the move to finish so the render tree is up-to-date
    await new Promise<void>((resolve) => {
      void map.once('moveend', () => {
        resolve();
      });
    });

    // 3) Build a small bbox around the stop's screen point for robust picking
    const pt = map.project([s.stopLon, s.stopLat]);
    const HIT = 6; // px hit radius; tweak 4..8 if needed
    const bbox: [[number, number], [number, number]] = [
      [pt.x - HIT, pt.y - HIT],
      [pt.x + HIT, pt.y + HIT],
    ];

    // 4) Query rendered features, filtering by exact stop_id
    const features = map.queryRenderedFeatures(bbox, {
      layers: ['stops-index'],
      filter: ['==', ['to-string', ['get', 'stop_id']], String(s.stopId)],
    });

    const stopFeature = features[0];
    if (stopFeature == null) {
      // fallback: still open popup with what we have
      setMapClickRouteData(null);
      setMapClickStopData({
        stop_id: s.stopId,
        stop_name: s.name,
        location_type: String(s.locationType ?? 0),
        longitude: String(s.stopLon),
        latitude: String(s.stopLat),
      });
      setSelectedStopId(s.stopId);
      return;
    }

    // 5) Open sticky popup with authoritative properties from the tile
    setMapClickRouteData(null);
    setMapClickStopData({
      ...stopFeature.properties,
      stop_id: s.stopId,
      stop_name: s.name,
      location_type: String(s.locationType ?? 0),
      longitude: String(s.stopLon),
      latitude: String(s.stopLat),
    });
    setSelectedStopId(s.stopId);
  };

  // Compute the right bounds (global vs filtered)
  const computeTargetBounds = (): LngLatBoundsLike | null => {
    const hasRouteFilter = filteredRoutes.length > 0;
    const hasTypeFilter = filteredRouteTypeIds.length > 0;
    if (!hasRouteFilter && !hasTypeFilter) return bounds;

    const boxes: LngLatBoundsLike[] = [];
    if (hasRouteFilter) {
      boxes.push(
        ...filteredRoutes
          .map((rid) => routeIdToBBoxRef.current[rid])
          .filter((b): b is LngLatBoundsLike => b != null),
      );
    } else if (hasTypeFilter) {
      boxes.push(
        ...filteredRouteTypeIds
          .map((rt) => routeTypeToBBoxRef.current[rt])
          .filter((b): b is LngLatBoundsLike => b != null),
      );
    }
    return extendBBoxes(boxes) ?? null;
  };

  // Auto-zoom when filters change (after precomputation is ready)
  useEffect(() => {
    if (preview) return; // honor preview mode
    const map = mapRef.current?.getMap();
    if (map == null) return;

    // Wait until precomputation has filled the BBox refs
    if (!precomputedReadyRef.current) return;

    const hasRouteFilter = filteredRoutes.length > 0;
    const hasTypeFilter = filteredRouteTypeIds.length > 0;

    if (!hasRouteFilter && !hasTypeFilter) {
      // No filters → back to dataset bounds (match original params)
      map.fitBounds(bounds, { padding: 40, duration: 500, maxZoom: 12 });
      return;
    }

    const target = computeTargetBounds();
    if (target != null) {
      map.fitBounds(target, { padding: 60, duration: 600 });
    } else {
      // If BBoxes are missing for the selection, fall back to dataset bounds
      map.fitBounds(bounds, { padding: 60, duration: 500 });
    }
    // include isScanning so we run once more when scanning completes
  }, [filteredRoutes, filteredRouteTypeIds]);

  const resetView = (): void => {
    const map = mapRef.current?.getMap();
    if (map == null) return;
    const target = computeTargetBounds();
    if (target != null) {
      map.fitBounds(target, { padding: 60, duration: 500 });
    } else {
      // fallback to dataset bounds
      map.fitBounds(bounds, { padding: 60, duration: 500 });
    }
  };

  useEffect(() => {
    if (!preview && refocusTrigger) {
      resetView();
    }
  }, [preview, refocusTrigger]);

  function handleCancelScan(): void {
    cancelRequestRef.current = true;
    setIsScanning(false);
    // clear all precomputed data
    routeIdToBBoxRef.current = {};
    routeTypeToBBoxRef.current = {};
    stopsByRouteIdRef.current = {};
    precomputedReadyRef.current = false;

    // reset map state
    const map = mapRef.current?.getMap();
    if (map != null) {
      map.fitBounds(bounds, { padding: 100, duration: 0 });
    }
  }

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
          {/* Hover/click info (top-left) */}
          <MapElement
            mapElements={mapElements}
            dataDisplayLimit={dataDisplayLimit}
          />

          {filteredRoutes.length > 0 && selectedRouteStops.length > 0 && (
            <SelectedRoutesStopsPanel
              filteredRoutes={filteredRoutes}
              selectedRouteStops={selectedRouteStops}
              selectedStopId={selectedStopId}
              focusStopFromPanel={(stopData) => {
                void focusStopFromPanel(stopData);
              }}
            />
          )}

          {isScanning && (
            <ScanningOverlay
              totalTiles={totalTiles}
              scannedTiles={scannedTiles}
              scanRowsCols={scanRowsCols}
              handleCancelScan={handleCancelScan}
              cancelRequestRef={cancelRequestRef}
            />
          )}

          <Map
            onClick={(event) => {
              handleMouseClick(event);
            }}
            onLoad={() => {
              if (didInitRef.current) return; // guard against re-entrancy
              didInitRef.current = true;
              precomp.registerRunOnMapIdle();
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
              'stops-index',
            ]}
            scrollZoom={true}
            dragPan={true}
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
                },
                routes: {
                  type: 'vector',
                  url: `pmtiles://${routesPmtilesUrl}`, // dynamic routes
                },
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
                RoutesWhiteLayer(filteredRouteTypeIds, theme),
                RouteLayer(filteredRoutes, filteredRouteTypeIds),
                StopLayer(hideStops, allSelectedRouteIds, stopRadius),
                RouteHighlightLayer(
                  mapClickRouteData?.route_id,
                  hoverInfo,
                  filteredRoutes,
                ),
                StopsHighlightLayer(
                  hoverInfo,
                  hideStops,
                  filteredRoutes,
                  mapClickStopData?.stop_id,
                  stopHighlightColorMap,
                ),
                StopsHighlightOuterLayer(
                  hoverInfo,
                  hideStops,
                  filteredRoutes,
                  theme,
                ),
                StopsIndexLayer(),
              ],
            }}
          >
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
            />
          </Map>
        </Box>
      </Box>
    </MapProvider>
  );
};
