/* eslint-disable */

import { useEffect, useMemo, useRef, useState } from "react";
import Map, { MapProvider, type MapRef, NavigationControl, ScaleControl } from "react-map-gl/maplibre";
import maplibregl, { type ExpressionSpecification, type LngLatBoundsLike } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";
import { type LatLngExpression } from "leaflet";
import { Box, Typography, useTheme } from "@mui/material";
import Draggable from 'react-draggable';

import { LinearProgress, CircularProgress } from "@mui/material";

import type { MapElementType } from "./MapElement";
import { MapElement, MapRouteElement, MapStopElement } from "./MapElement";
import { MapDataPopup } from "./Map/MapDataPopup";
import type { GtfsRoute } from "../types";
import { useTranslation } from "react-i18next";
import { createPrecomputation, extendBBoxes, type RouteIdsInput } from "../utils/precompute";

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
                                       refocusTrigger=false,
                                       stopRadius = 3,
                                       preview = true
                                     }: GtfsVisualizationMapProps): JSX.Element => {
  const { stopsPmtilesUrl, routesPmtilesUrl } = useMemo(() => {
    const baseUrl = latestDataset?.hosted_url
      ? latestDataset.hosted_url.replace(/[^/]+$/, "")
      : undefined;
    const stops = `${baseUrl}/pmtiles/stops.pmtiles`;
    const routes = `${baseUrl}/pmtiles/routes.pmtiles`;
    return { stopsPmtilesUrl: stops, routesPmtilesUrl: routes };
  }, [latestDataset?.id, latestDataset?.stable_id]);

  const theme = useTheme();
  const { t } = useTranslation("feeds");
  const [hoverInfo, setHoverInfo] = useState<string[]>([]);
  const [mapElements, setMapElements] = useState<MapElementType[]>([]);
  const [mapClickRouteData, setMapClickRouteData] = useState<Record<string, string> | null>(null);
  const [mapClickStopData, setMapClickStopData] = useState<Record<string, string> | null>(null);

  // Stable list of all stops matched to selected routes (independent of hover)
  const [selectedRouteStops, setSelectedRouteStops] = useState<MapStopElement[]>([]);

  const mapRef = useRef<MapRef>(null);
  const didInitRef = useRef(false);
  const routeStopsPanelNodeRef = useRef<HTMLDivElement | null>(null);

  // Scanning overlay state
  const [isScanning, setIsScanning] = useState(false);
  const [scannedTiles, setScannedTiles] = useState(0);
  const [totalTiles, setTotalTiles] = useState(0);
  const [scanRowsCols, setScanRowsCols] = useState<{ rows: number; cols: number } | null>(null);

  // Selected stop id from the panel (for cute highlight)
  const [selectedStopId, setSelectedStopId] = useState<string | null>(null);

  // Build routeId -> color map from the currently shown hover/click panels
  const routeIdToColorMap: Record<string, string> = {};
  mapElements.forEach((el) => {
    if (!el.isStop) {
      const routeElement: MapRouteElement = el as MapRouteElement;
      if (routeElement.routeId && routeElement.routeColor) {
        routeIdToColorMap[routeElement.routeId] = routeElement.routeColor;
      }
    }
  });
  // Pull colors for the currently filtered route IDs (from props.routes)
  const filteredRouteColors: Record<string, string> = useMemo(() => {
    const m: Record<string, string> = {};
    for (const rid of filteredRoutes) {
      const r = (routes ?? []).find(rr => String(rr.routeId) === String(rid));
      // strip leading '#' because generateStopColorExpression expects raw hex
      if (r?.color) m[String(rid)] = String(r.color).replace(/^#/, "");
    }
    return m;
  }, [filteredRoutes, routes]);

  // Merge: filtered-route colors (take priority) + hover/click colors
  const stopHighlightColorMap: Record<string, string> = {
    ...routeIdToColorMap,
    ...filteredRouteColors,
  };


  function generateStopColorExpression(
    routeIdToColor: Record<string, string>,
    fallback = '#888',
  ): ExpressionSpecification {
    const expression: any[] = ["case"];
    Object.entries(routeIdToColor).forEach(([routeId, color]) => {
      expression.push(["in", `"${routeId}"`, ["get", "route_ids"]], `#${color}`);
    });
    if (expression.length === 1) {
      return fallback as unknown as ExpressionSpecification;
    }

    expression.push(fallback); // Add fallback color
    return expression as ExpressionSpecification;
  }

  const routeTypeFilter: ExpressionSpecification | boolean =
    filteredRouteTypeIds.length > 0
      ? ['in', ['get', 'route_type'], ['literal', filteredRouteTypeIds]]
      : true; // if no filter applied, show all

  const handleMouseClick = (event: maplibregl.MapLayerMouseEvent): void => {
    const map = mapRef.current?.getMap();
    if (map != undefined) {
      // Get the features under the mouse pointer
      const features = map.queryRenderedFeatures(event.point, {
        layers: ['stops-index', 'routes-highlight'],
      });

      const selectedStop = features.find((feature) => feature.layer.id === "stops-index");
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

      const selectedRoute = features.find((f) => f.layer.id === 'routes-highlight');
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

  const handlePopupClose = () => {
    setMapClickRouteData(null);
    setMapClickStopData(null);
    setSelectedStopId(null);
  };

  const handleMouseMove = (event: maplibregl.MapLayerMouseEvent): void => {
    const map = mapRef.current?.getMap();
    const next: MapElementType[] = [];
    if (map != undefined) {
      const features = map.queryRenderedFeatures(event.point, {
        layers: ["stops", "routes"],
      });

      if (features.length > 0 || mapClickRouteData != null || mapClickStopData != null) {
        if (mapClickRouteData != null) {
          next.push({
            isStop: false,
            name: mapClickRouteData.route_long_name,
            routeType: Number(mapClickRouteData.route_type),
            routeColor: mapClickRouteData.route_color,
            routeTextColor: mapClickRouteData.route_text_color,
            routeId: mapClickRouteData.route_id,
          } as MapRouteElement);
        }
        if (mapClickStopData != null) {
          next.push({
            isStop: true,
            name: mapClickStopData.stop_name,
            locationType: Number(mapClickStopData.location_type),
            stopId: mapClickStopData.stop_id,
          } as MapStopElement);
        }
        features.forEach((feature) => {
          if (feature.layer.id === "stops") {
            next.push({
              isStop: true,
              name: feature.properties.stop_name,
              locationType: Number(feature.properties.location_type),
              stopId: feature.properties.stop_id,
            } as MapStopElement);
          } else {
            next.push({
              isStop: false,
              name: feature.properties.route_long_name,
              routeType: feature.properties.route_type,
              routeColor: feature.properties.route_color,
              routeTextColor: feature.properties.route_text_color,
              routeId: feature.properties.route_id,
            } as MapRouteElement);
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

  const getBoundsFromCoordinates = (coordinates: Array<[number, number]>): LngLatBoundsLike => {
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

  const bounds: LngLatBoundsLike = getBoundsFromCoordinates(polygon as Array<[number, number]>);

// route IDs coming from selected route types
  const routeIdsFromTypes =
    filteredRouteTypeIds.length > 0
      ? (routes ?? [])
        .filter(r => filteredRouteTypeIds.includes(String(r.routeType)))
        .map(r => String(r.routeId))
      : [];

  // union of explicit route IDs + those implied by selected types
  const allSelectedRouteIds = [...filteredRoutes, ...routeIdsFromTypes];

  // Base filter for visible stops (main "stops" layer)
  const stopsBaseFilter: ExpressionSpecification | boolean = hideStops
    ? false
    : allSelectedRouteIds.length === 0
      ? true // no filters → show all
      : ([
        "any",
        ...allSelectedRouteIds.map(
          (id) => ["in", `\"${id}\"`, ["get", "route_ids"]] as any // route_ids stored as quoted-string list
        ),
      ] as any);


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
      out.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
      setSelectedRouteStops(out);
      return;
    }
  }, [filteredRoutes]);

  // tries a single instant expand-to-bounds if nothing is rendered yet
  const fitExpandAttemptRef = useRef(0);

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

  // Extract route_ids list from the PMTiles property (stringified JSON)
  function extractRouteIds(val: RouteIdsInput): string[] {
    if (Array.isArray(val)) return val.map(String);
    if (typeof val === "string") {
      try {
        const parsed = JSON.parse(val);
        if (Array.isArray(parsed)) return parsed.map(String);
      } catch {}
      // fallback: pull "quoted" tokens
      const out: string[] = [];
      val.replace(/"([^"]+)"/g, (_: any, id: string) => {
        out.push(id);
        return "";
      });
      if (out.length) return out;
      // fallback2: CSV-ish
      return val
        .split(",")
        .map((s: string) => s.trim())
        .filter(Boolean);
    }
    return [];
  }

  // --- instantiate the extracted precomputation with identical behavior ---
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
    ]
  );

  // Helper values for overlay
  const progressPct = totalTiles > 0 ? Math.min(100, Math.round((scannedTiles / totalTiles) * 100)) : 0;
  const isLarge = totalTiles >= 80;
  const rowsColsText =
    scanRowsCols ? `${scanRowsCols.rows} rows × ${scanRowsCols.cols} cols` : undefined;

  // Helper to focus & stick a stop from the panel
  const focusStopFromPanel = async (s: MapStopElement) => {
    const map = mapRef.current?.getMap();
    if (!map) return;

    // 1) Move the camera
    map.easeTo({
      center: [s.stopLon, s.stopLat],
      zoom: Math.max(map.getZoom(), 13),
      duration: 400,
    });

    // 2) Wait for the move to finish so the render tree is up-to-date
    await new Promise<void>((resolve) => map.once("moveend", () => resolve()));

    // 3) Build a small bbox around the stop's screen point for robust picking
    const pt = map.project([s.stopLon, s.stopLat]);
    const HIT = 6; // px hit radius; tweak 4..8 if needed
    const bbox: [[number, number], [number, number]] = [
      [pt.x - HIT, pt.y - HIT],
      [pt.x + HIT, pt.y + HIT],
    ];

    // 4) Query rendered features, filtering by exact stop_id
    const features = map.queryRenderedFeatures(bbox, {
      layers: ["stops-index"],
      filter: ["==", ["to-string", ["get", "stop_id"]], String(s.stopId)] as any,
    });

    const stopFeature = features[0];
    if (!stopFeature) {
      // fallback: still open popup with what we have
      setMapClickRouteData(null);
      setMapClickStopData({
        stop_id: s.stopId,
        stop_name: s.name,
        location_type: String(s.locationType ?? 0),
        longitude: s.stopLon,
        latitude: s.stopLat,
      } as any);
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
      longitude: s.stopLon,
      latitude: s.stopLat,
    } as any);
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
          .filter((b): b is LngLatBoundsLike => b != null)
      );
    } else if (hasTypeFilter) {
      boxes.push(
        ...filteredRouteTypeIds
          .map((rt) => routeTypeToBBoxRef.current[rt])
          .filter((b): b is LngLatBoundsLike => b != null)
      );
    }
    return extendBBoxes(boxes) ?? null;
  };

  // Auto-zoom when filters change (after precomputation is ready)
  useEffect(() => {
    if (preview) return; // honor preview mode
    const map = mapRef.current?.getMap();
    if (!map) return;

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
    if (target) {
      map.fitBounds(target, { padding: 60, duration: 600 });
    } else {
      // If BBoxes are missing for the selection, fall back to dataset bounds
      map.fitBounds(bounds, { padding: 60, duration: 500 });
    }
    // include isScanning so we run once more when scanning completes
  }, [filteredRoutes, filteredRouteTypeIds]);


  // Handler to reset view
  const resetView = () => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    const target = computeTargetBounds();
    if (target) {
      map.fitBounds(target, { padding: 60, duration: 500});
    } else {
      // fallback to dataset bounds
      map.fitBounds(bounds, { padding: 60, duration: 500});
    }
  };

  if (!preview) {
    useEffect(() => {
      if (refocusTrigger) {
        resetView();
      }
    }, [refocusTrigger]);
  }


  return (
    <MapProvider>
      <Box sx={{ display: "flex", height: "100%" }}>
        <Box
          sx={{
            width: "100%",
            height: "100%",
            position: "relative",
            borderColor: theme.palette.primary.main,
            borderRadius: "5px",
          }}
        >
          {/* Hover/click info (top-left) */}
          <MapElement mapElements={mapElements} dataDisplayLimit={dataDisplayLimit} />

          {/* Selected route stops panel */}
          {filteredRoutes.length > 0 && selectedRouteStops.length > 0 && (
            <Draggable
              nodeRef={routeStopsPanelNodeRef}
              handle=".drag-handle"
              bounds="parent"
            >
              <Box
                ref={routeStopsPanelNodeRef}
                sx={{
                  position: "absolute",
                  right: "10px",
                  top: "25%",
                  height: "50%",
                  width: 250,
                  transform: "translateY(-0%)",
                  zIndex: 1000,
                  bgcolor: theme.palette.background.default,
                  borderRadius: "12px",
                  boxShadow: "1px 1px 8px rgba(0,0,0,0.25)",
                  display: "flex",
                  flexDirection: "column",
                  overflow: "hidden",
                }}
              >
                <Box
                  sx={{ p: 1.5, borderBottom: `1px solid ${theme.palette.divider}`, cursor: 'move' }}
                  className="drag-handle"
                >
                  <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                    {t("selectedRouteStops.title", { count: filteredRoutes.length })} ({selectedRouteStops.length})
                  </Typography>
                  <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                    {t("selectedRouteStops.routeIds", { count: filteredRoutes.length })}: {filteredRoutes.join(" | ")}
                  </Typography>
                </Box>
                <Box sx={{ flex: 1, overflowY: "auto", p: 1 }}>
                  {selectedRouteStops.map((s) => {
                    const isActive = selectedStopId === s.stopId;
                    return (
                      <Box
                        key={s.stopId}
                        role="button"
                        tabIndex={0}
                        aria-selected={isActive ? "true" : "false"}
                        onClick={() => focusStopFromPanel(s)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") focusStopFromPanel(s); // NEW: keyboard support
                        }}
                        sx={{
                          py: 0.9,
                          px: 1.1,
                          mb: 0.5,
                          borderRadius: "10px",
                          border: isActive ? `2px solid ${theme.palette.primary.main}` : `1px solid ${theme.palette.divider}`,
                          backgroundColor: isActive ? theme.palette.action.selected : "transparent",
                          transition: "background-color 120ms ease, border-color 120ms ease, box-shadow 120ms ease",
                          cursor: "pointer",
                          "&:hover": { backgroundColor: theme.palette.action.hover },
                          boxShadow: isActive ? "0 0 0 2px rgba(0,0,0,0.06) inset" : "none",
                        }}
                      >
                        <Typography variant="body2" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                          {s.name}
                        </Typography>
                        <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                          {t("selectedRouteStops.stopId")} {s.stopId}
                        </Typography>
                      </Box>
                    );
                  })}
                </Box>
              </Box>
            </Draggable>
          )}


          {/* Scanning overlay */}
          {isScanning && (
            <Box
              role="status"
              aria-live="polite"
              sx={{
                position: "absolute",
                inset: 0,
                zIndex: 1200,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                backdropFilter: "blur(2px)",
                background:
                  "linear-gradient(180deg, rgba(255,255,255,0.65) 0%, rgba(255,255,255,0.55) 100%)",
              }}
            >
              <Box
                sx={{
                  width: 420,
                  maxWidth: "90%",
                  bgcolor: theme.palette.background.paper,
                  borderRadius: "14px",
                  boxShadow: "0 8px 24px rgba(0,0,0,0.18)",
                  border: `1px solid ${theme.palette.divider}`,
                  p: 2.25,
                }}
              >
                <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, mb: 1 }}>
                  <CircularProgress size={20} thickness={4} />
                  <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                    {isLarge ? t("scanning.titleLarge") : t("scanning.title")}
                  </Typography>
                </Box>

                <Typography variant="body2" sx={{ mb: 1, color: theme.palette.text.secondary }}>
                  {isLarge ? t("scanning.bodyLarge") : t("scanning.body")}
                </Typography>

                {rowsColsText && (
                  <Typography variant="caption" sx={{ display: "block", mb: 1, opacity: 0.9 }}>
                    {t("scanning.gridTile", {
                      grid: rowsColsText,
                      tile: Math.min(scannedTiles, totalTiles),
                      total: totalTiles,
                    })}
                  </Typography>
                )}

                <LinearProgress
                  variant="determinate"
                  value={progressPct}
                  sx={{
                    height: 8,
                    borderRadius: "999px",
                    mb: 1,
                  }}
                />

                <Typography
                  variant="caption"
                  sx={{ color: theme.palette.text.secondary }}
                >
                  {t("scanning.percentComplete", { percent: progressPct })}
                </Typography>
              </Box>
            </Box>
          )}

          <Map
            onClick={(event) => handleMouseClick(event)}
            onLoad={() => {
              if (didInitRef.current) return;  // guard against re-entrancy
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
              'stops-index'
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
                  id: "simple-tiles",
                  type: "raster",
                  source: "raster-tiles",
                  minzoom: 0,
                  maxzoom: 22,
                },
                {
                  id: "routes-white",
                  source: "routes",
                  filter: routeTypeFilter,
                  "source-layer": "routesoutput",
                  type: "line",
                  paint: {
                    "line-color": theme.palette.background.paper,
                    "line-width": [
                      "match",
                      ["get", "route_type"],
                      "3",
                      4,
                      "1",
                      15,
                      3,
                    ],
                  },
                },
                {
                  id: "routes",
                  filter: routeTypeFilter,
                  source: "routes",
                  "source-layer": "routesoutput",
                  type: "line",
                  paint: {
                    "line-color": ["concat", "#", ["get", "route_color"]],
                    "line-width": [
                      "match",
                      ["get", "route_type"],
                      "3",
                      1,
                      "1",
                      4,
                      3,
                    ],
                    "line-opacity": [
                      "case",
                      [
                        "any",
                        ["==", filteredRoutes.length, 0],
                        ["in", ["get", "route_id"], ["literal", filteredRoutes]],
                      ],
                      0.4,
                      0.1,
                    ],
                  },
                  layout: {
                    "line-sort-key": [
                      "match",
                      ["get", "route_type"],
                      "1",
                      3,
                      "3",
                      2,
                      0,
                    ],
                  },
                },
                {
                  id: "stops",
                  filter: stopsBaseFilter,
                  source: "sample",
                  "source-layer": "stopsoutput",
                  type: "circle",
                  paint: {
                    "circle-radius": stopRadius,
                    "circle-color": "#000000",
                    "circle-opacity": 0.4,
                  },
                  minzoom: 12,
                  maxzoom: 22,
                },
                {
                  id: "routes-highlight",
                  source: "routes",
                  "source-layer": "routesoutput",
                  type: "line",
                  paint: {
                    "line-color": ["concat", "#", ["get", "route_color"]],
                    "line-opacity": 1,
                    "line-width": [
                      "match",
                      ["get", "route_type"],
                      "3",
                      5,
                      "1",
                      6,
                      3,
                    ],
                  },
                  filter: [
                    "any",
                    ["in", ["get", "route_id"], ["literal", hoverInfo]],
                    ["in", ["get", "route_id"], ["literal", filteredRoutes]],
                    ["in", ["get", "route_id"], ["literal", mapClickRouteData?.route_id ?? ""]],
                  ],
                },
                {
                  id: 'stops-highlight',
                  source: "sample",
                  "source-layer": "stopsoutput",
                  type: "circle",
                  paint: {
                    "circle-radius": 7,
                    "circle-color": generateStopColorExpression(stopHighlightColorMap) as ExpressionSpecification,
                    "circle-opacity": 1,
                  },
                  minzoom: 10,
                  maxzoom: 22,
                  filter: hideStops
                    ? !hideStops
                    : [
                      "any",
                      ["in", ["get", "stop_id"], ["literal", hoverInfo]],
                      ["==", ["get", "stop_id"], ["literal", mapClickStopData?.stop_id ?? ""]],
                      [
                        "any",
                        ...filteredRoutes.map((id) => {
                          return ["in", `\"${id}\"`, ["get", "route_ids"]] as any;
                        }),
                      ],
                      [
                        "any",
                        ...hoverInfo.map((id) => {
                          return ["in", `\"${id}\"`, ["get", "route_ids"]] as any;
                        }),
                      ],
                    ],
                },
                {
                  id: "stops-highlight-outer",
                  source: "sample",
                  "source-layer": "stopsoutput",
                  type: "circle",
                  paint: {
                    "circle-radius": 3,
                    "circle-color": theme.palette.background.paper,
                    "circle-opacity": 1,
                  },
                  filter: hideStops
                    ? !hideStops
                    : [
                      "any",
                      ["in", ["get", "stop_id"], ["literal", hoverInfo]],
                      [
                        "any",
                        ...filteredRoutes.map((id) => {
                          return ["in", `\"${id}\"`, ["get", "route_ids"]] as any;
                        }),
                      ],
                      [
                        "any",
                        ...hoverInfo.map((id) => {
                          return ["in", `\"${id}\"`, ["get", "route_ids"]] as any;
                        }),
                      ],
                    ],
                },
                {
                  id: "stops-index",
                  source: "sample",
                  "source-layer": "stopsoutput",
                  type: "circle",
                  paint: {
                    "circle-color": "rgba(0,0,0, 0)",
                    "circle-radius": 1,
                  },
                },
              ],
            }}
          >
            <ScaleControl position="bottom-left" unit="metric" />
            <NavigationControl
              position="top-right"
              showCompass={true}
              showZoom={true}
              style={{
                backgroundColor: "white",
                marginTop: "72px",
                marginRight: "15px",
                boxShadow:
                  "rgba(0, 0, 0, 0.2) 0px 3px 5px -1px, rgba(0, 0, 0, 0.14) 0px 6px 10px 0px, rgba(0, 0, 0, 0.12) 0px 1px 18px 0px",
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
