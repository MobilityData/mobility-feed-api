// precompute.ts
import type { RefObject } from 'react';
import type { MapRef } from 'react-map-gl/maplibre';
import { type LngLatBoundsLike } from 'maplibre-gl';
import type maplibregl from 'maplibre-gl';
import { type MapStopElement } from '../components/MapElement';

export type RouteIdsInput = string | string[] | number[] | null | undefined;

class CancellationError extends Error {
  constructor(message: string = 'Operation cancelled.') {
    super(message);
    this.name = 'CancellationError'; // Set a custom name for the error type
  }
}

export interface PrecomputeDeps {
  // runtime inputs
  mapRef: RefObject<MapRef>;
  bounds: LngLatBoundsLike;
  preview: boolean;
  cancelRequestRef: RefObject<boolean>;

  // extractors / helpers
  extractRouteIds: (val: RouteIdsInput) => string[];

  // state setters
  setIsScanning: (v: boolean) => void;
  setScanRowsCols: (v: { rows: number; cols: number } | null) => void;
  setScannedTiles: (v: number) => void;
  setTotalTiles: (v: number) => void;

  // refs to persist computed data
  routeIdToBBoxRef: React.MutableRefObject<Record<string, LngLatBoundsLike>>;
  routeTypeToBBoxRef: React.MutableRefObject<Record<string, LngLatBoundsLike>>;
  stopsByRouteIdRef: React.MutableRefObject<Record<string, MapStopElement[]>>;
  precomputedReadyRef: React.MutableRefObject<boolean>;

  // routeId -> routeType mapping
  routeIdToType: Record<string, string>;
}

/** Small helper: wait once for a map event */
async function once(map: maplibregl.Map, ev: string): Promise<void> {
  await new Promise<void>(
    // eslint-disable-next-line @typescript-eslint/no-misused-promises,no-async-promise-executor
    async (resolve) =>
      await map.once(ev, () => {
        resolve();
      }),
  );
}

// Extend helpers for [minLng,minLat,maxLng,maxLat]
function extendBBox(
  bb: LngLatBoundsLike | undefined,
  lng: number,
  lat: number,
): LngLatBoundsLike {
  if (bb == null) return [lng, lat, lng, lat];
  const b = bb as [number, number, number, number];
  return [
    Math.min(b[0], lng),
    Math.min(b[1], lat),
    Math.max(b[2], lng),
    Math.max(b[3], lat),
  ];
}

export function extendBBoxes(
  boxes: LngLatBoundsLike[],
): LngLatBoundsLike | null {
  if (boxes.length === 0) return null;
  let u = boxes[0] as [number, number, number, number];
  for (let i = 1; i < boxes.length; i++) {
    const b = boxes[i] as [number, number, number, number];
    u = [
      Math.min(u[0], b[0]),
      Math.min(u[1], b[1]),
      Math.max(u[2], b[2]),
      Math.max(u[3], b[3]),
    ];
  }
  return u;
}

export function createPrecomputation(deps: PrecomputeDeps): {
  runPrecomputation: () => Promise<void>;
  registerRunOnMapIdle: () => void;
} {
  const {
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
  } = deps;

  /** Public API: identical behavior, just moved out */
  const runPrecomputation = async (): Promise<void> => {
    // ---- SWIPE THE MAP OVER A GRID AT A FIXED ZOOM AND COLLECT FEATURES ----
    const map = mapRef.current?.getMap();
    if (map == null) return;

    // Save camera to restore later
    const prev = {
      center: map.getCenter(),
      zoom: map.getZoom(),
      bearing: map.getBearing(),
      pitch: map.getPitch(),
    };

    // Choose a zoom where stops will exist in the tiles (tweak if needed)
    const SWEEP_ZOOM = 10; // fixed zoom for the sweep
    const OVERLAP = 0.2; // 20% overlap between viewports to avoid gaps

    // Jump once to dataset center at SWEEP_ZOOM to measure view span
    const [minLng, minLat, maxLng, maxLat] = bounds as [
      number,
      number,
      number,
      number,
    ];
    const centerLng = (minLng + maxLng) / 2;
    const centerLat = (minLat + maxLat) / 2;
    map.jumpTo({
      center: [centerLng, centerLat],
      zoom: SWEEP_ZOOM,
      bearing: prev.bearing,
      pitch: prev.pitch,
    });
    await once(map, 'idle');

    // Determine viewport geographic span at this zoom
    const canvas = map.getCanvas();
    const tl = map.unproject([0, 0]);
    const br = map.unproject([canvas.width, canvas.height]);
    const viewLngSpan = Math.abs(br.lng - tl.lng);
    const viewLatSpan = Math.abs(tl.lat - br.lat);

    const dataLngSpan = maxLng - minLng;
    const dataLatSpan = maxLat - minLat;

    // How many columns/rows to cover the whole dataset with some overlap
    const cols = Math.max(
      1,
      Math.ceil(dataLngSpan / (viewLngSpan * (1 - OVERLAP))),
    );
    const rows = Math.max(
      1,
      Math.ceil(dataLatSpan / (viewLatSpan * (1 - OVERLAP))),
    );

    // Initialize scanning overlay
    setIsScanning(true);
    setScanRowsCols({ rows, cols });
    setScannedTiles(0);
    setTotalTiles(rows * cols);

    const lngStep = dataLngSpan / cols;
    const latStep = dataLatSpan / rows;

    const seenStopIds = new Set<string>();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const featsAll: any[] = [];

    for (let r = 0; r < rows; r++) {
      const cy = minLat + (r + 0.5) * latStep;
      for (let c = 0; c < cols; c++) {
        if (cancelRequestRef.current === true) {
          // user requested to cancel
          throw new CancellationError();
        }
        const cx = minLng + (c + 0.5) * lngStep;

        map.jumpTo({
          center: [cx, cy],
          zoom: SWEEP_ZOOM,
          bearing: prev.bearing,
          pitch: prev.pitch,
        });
        await once(map, 'idle');

        const bbox: [[number, number], [number, number]] = [
          [0, 0],
          [canvas.width, canvas.height],
        ];
        const partial = map.queryRenderedFeatures(bbox, {
          layers: ['stops-index'],
        });

        // Dedup by stop_id as we aggregate
        for (const f of partial) {
          const sid = String(f.properties?.stop_id ?? '');
          if (sid === '' || seenStopIds.has(sid)) continue;
          seenStopIds.add(sid);
          featsAll.push(f);
        }

        // progress update (tile-by-tile)
        const idx = r * cols + c + 1;
        setScannedTiles(idx);
      }
    }

    // restore camera
    map.jumpTo(prev);
    await once(map, 'idle');

    // ---- Build indexes from collected features (same logic) ----
    const idToBBox: Record<string, LngLatBoundsLike> = {};
    const typeToBBox: Record<string, LngLatBoundsLike> = {};
    const byRouteId: Record<string, MapStopElement[]> = {};

    for (const f of featsAll) {
      const g = f.geometry;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const geometryJson = g as { type: string; coordinates: any };

      if (
        g == null ||
        g.type !== 'Point' ||
        !Array.isArray(geometryJson.coordinates) ||
        typeof geometryJson.coordinates[0] !== 'number' ||
        typeof geometryJson.coordinates[1] !== 'number'
      ) {
        continue;
      }

      const [lng, lat] = geometryJson.coordinates as [number, number];
      const stopId = String(f.properties?.stop_id ?? '');
      const stopName = String(f.properties?.stop_name ?? '');
      const locationType = Number(f.properties?.location_type ?? 0);

      const routeIds = extractRouteIds(f.properties?.route_ids);
      if (routeIds.length === 0) continue;

      for (const rid of routeIds) {
        // bbox per routeId
        idToBBox[rid] = extendBBox(idToBBox[rid], lng, lat);

        // stops per routeId
        byRouteId[rid] ??= [];
        if (
          stopId != null &&
          !byRouteId[rid].some((s) => s.stopId === stopId)
        ) {
          const lat2 = Number(f.geometry?.coordinates?.[1] ?? 0);
          const lon2 = Number(f.geometry?.coordinates?.[0] ?? 0);
          if (isNaN(lat2) || isNaN(lon2) || lat2 === 0 || lon2 === 0) {
          }
          byRouteId[rid].push({
            isStop: true,
            name: stopName,
            locationType,
            stopId,
            stopLat: lat2,
            stopLon: lon2,
          });
        }

        // bbox per routeType (via routes prop map)
        const rt = routeIdToType[rid];
        if (rt != null) {
          typeToBBox[rt] = extendBBox(typeToBBox[rt], lng, lat);
        }
      }
    }

    // Persist
    routeIdToBBoxRef.current = idToBBox;
    routeTypeToBBoxRef.current = typeToBBox;
    Object.keys(byRouteId).forEach((rid) => {
      byRouteId[rid].sort((a, b) =>
        a.name.localeCompare(b.stopId, undefined, { sensitivity: 'base' }),
      );
    });
    stopsByRouteIdRef.current = byRouteId;

    precomputedReadyRef.current = true;

    // finalize overlay
    setIsScanning(false);
    setScanRowsCols(null);
  };

  /** Public API: identical behavior — fit to bounds, run once on first idle */
  const registerRunOnMapIdle = (): void => {
    if (preview) return; // skip all precomputation in preview mode
    const map = mapRef.current?.getMap();
    if (map == null) return;
    // ensure we’re looking at the dataset so tiles will load
    map.fitBounds(bounds, { padding: 100, duration: 0 });

    void map.once('idle', () => {
      void runPrecomputation()
        .then(() => {})
        .catch((e) => {
          if (e.name === 'CancellationError') {
            // cancelled by user, ignore
          }
        });
    });
  };
  return { runPrecomputation, registerRunOnMapIdle };
}
