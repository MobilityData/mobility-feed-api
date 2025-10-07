import React, {
  useState,
  useMemo,
  useEffect,
  useCallback,
  useLayoutEffect,
  useRef,
} from 'react';
import {
  TextField,
  Checkbox,
  ListItemText,
  ListItemIcon,
  Typography,
  Box,
  ListItemButton,
  Skeleton,
} from '@mui/material';
import { type GtfsRoute } from '../types';
import { debounce } from 'lodash';
import { List, type RowComponentProps } from 'react-window';

interface RouteSelectorProps {
  routes: GtfsRoute[];
  selectedRouteIds?: string[];
  onSelectionChange?: (selectedRoutes: string[]) => void;
}

type PreparedRoute = GtfsRoute & {
  _nameLower: string;
  _idStr: string;
  _idLower: string;
};

interface RowProps {
  routes: PreparedRoute[];
  selectedRoutes: string[];
  onToggle: (routeId: string | undefined) => void;
}

function RowComponent({
  index,
  routes,
  selectedRoutes,
  onToggle,
  style,
}: RowComponentProps<RowProps>): React.ReactElement {
  const route = routes[index];
  const checked = selectedRoutes.includes(route.routeId ?? '');
  return (
    <div style={style}>
      <ListItemButton
        key={route.routeId}
        sx={{ pl: 0, pr: 1 }}
        onClick={() => {
          onToggle(route.routeId);
        }}
        dense
      >
        <ListItemIcon sx={{ minWidth: 34 }}>
          <Checkbox
            edge='start'
            checked={checked}
            tabIndex={-1}
            disableRipple
          />
        </ListItemIcon>
        <ListItemText
          primary={
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Box
                sx={{
                  width: 16,
                  height: 16,
                  backgroundColor: route.color ?? '#000',
                  borderRadius: '4px',
                  mr: 1,
                  border: '1px solid #999',
                  flex: '0 0 auto',
                }}
              />
              <Typography variant='inherit' sx={{ flex: 1, minWidth: 0 }}>
                {route.routeId} - {route.routeName}
              </Typography>
            </Box>
          }
        />
      </ListItemButton>
    </div>
  );
}

export default function RouteSelector({
  routes,
  selectedRouteIds = [],
  onSelectionChange,
}: RouteSelectorProps): React.ReactElement {
  const [search, setSearch] = useState('');
  const [inputValue, setInputValue] = useState('');
  const [selectedRoutes, setSelectedRoutes] =
    useState<string[]>(selectedRouteIds);
  const [isSearching, setIsSearching] = useState(false);
  const [listWidth, setListWidth] = useState<number>(0);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const measurerHostRef = useRef<HTMLDivElement | null>(null);
  const heightCacheRef = useRef<Map<string, number>>(new Map());

  // Track container width (pre-measure before first list render)
  useLayoutEffect(() => {
    if (containerRef.current == null) return;
    const el = containerRef.current;
    const ro = new ResizeObserver((entries) => {
      const w = Math.ceil(entries[0].contentRect.width);
      if (w !== listWidth) {
        setListWidth(w);
        heightCacheRef.current.clear(); // width changed → invalidate cache
      }
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
    };
  }, [listWidth]);

  // Debounced search input -> committed search term
  const debouncedSetSearch = useMemo(
    () =>
      debounce((val: string) => {
        setSearch(val);
        setIsSearching(false);
      }, 500),
    [],
  );

  useEffect(() => {
    setIsSearching(true);
    debouncedSetSearch(inputValue);
    return () => {
      debouncedSetSearch.cancel();
    };
  }, [inputValue, debouncedSetSearch]);

  // Keep internal selection in sync with controlled prop
  useEffect(() => {
    setSelectedRoutes([...selectedRouteIds]);
  }, [selectedRouteIds]);

  // Prepare routes for faster filtering (sorted + lowercase caches)
  const preparedRoutes = useMemo<PreparedRoute[]>(() => {
    const copy = [...routes];
    copy.sort((a, b) => (a.routeId ?? '').localeCompare(b.routeId ?? ''));
    return copy.map((r) => ({
      ...r,
      _nameLower: (r.routeName ?? '').toLowerCase(),
      _idStr: r.routeId ?? '',
      _idLower: (r.routeId ?? '').toLowerCase(),
    }));
  }, [routes]);

  // Filtered routes based on committed search term
  const filteredRoutes = useMemo(() => {
    const q = (search ?? '').trim().toLowerCase();
    if (q === '') return preparedRoutes;
    return preparedRoutes.filter(
      (route) => route._nameLower.includes(q) || route._idLower.includes(q),
    );
  }, [search, preparedRoutes]);

  const handleToggle = useCallback(
    (routeId: string | undefined): void => {
      if (routeId == undefined) return;
      setSelectedRoutes((prev) => {
        const newSelection = prev.includes(routeId)
          ? prev.filter((id) => id !== routeId)
          : [...prev, routeId];

        onSelectionChange?.(newSelection);
        return newSelection;
      });
    },
    [onSelectionChange],
  );

  // Compute row height before render using an offscreen measurer
  const LEFT_UI_WIDTH = 42 + 16 + 8 + 16; // checkbox + color swatch + margins/padding

  const ensureMeasureNode = (): HTMLDivElement | null => {
    const host = measurerHostRef.current;
    if (host == null) return null;
    let node = host.firstChild as HTMLDivElement | null;
    if (node == null) {
      node = document.createElement('div');
      node.style.position = 'absolute';
      node.style.visibility = 'hidden';
      node.style.pointerEvents = 'none';
      node.style.left = '0';
      node.style.top = '0';
      node.style.boxSizing = 'border-box';
      node.style.whiteSpace = 'pre-wrap';
      node.style.wordBreak = 'break-word';
      node.style.font = 'inherit';
      node.style.padding = '0';
      node.style.margin = '0';
      host.appendChild(node);
    }
    return node;
  };

  const rowHeight = useCallback(
    (index: number, rowProps: RowProps): number => {
      const width = listWidth ?? 0;
      if (width === 0) return 48;

      const route = rowProps.routes[index];
      const cacheKey = `${width}|${route.routeId ?? ''}|${
        route.routeName ?? ''
      }`;

      const cached = heightCacheRef.current.get(cacheKey);
      if (cached != null) return cached;

      const node = ensureMeasureNode();
      if (node == null) return 48;

      const textWidth = Math.max(80, width - LEFT_UI_WIDTH);
      node.style.width = `${textWidth}px`;
      node.style.fontSize = '14px';
      node.textContent = `${route.routeId} - ${route.routeName ?? ''}`;

      const textHeight = Math.ceil(node.offsetHeight);
      const computed = Math.max(40, textHeight + 16); // 8px padding top + bottom

      heightCacheRef.current.set(cacheKey, computed);
      return computed;
    },
    [listWidth],
  );

  return (
    <Box
      sx={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        minHeight: '300px',
        overflow: 'hidden',
      }}
    >
      <Typography variant='subtitle2' sx={{ m: 0 }}>
        {filteredRoutes.length} route{filteredRoutes.length !== 1 ? 's' : ''}
      </Typography>

      <TextField
        fullWidth
        size='small'
        variant='outlined'
        placeholder='Search routes...'
        value={inputValue}
        onChange={(e) => {
          setInputValue(e.target.value);
        }}
        sx={{ mb: 1 }}
      />

      {/* Host for width tracking + hidden measurer */}
      <Box
        ref={containerRef}
        sx={{ flex: 1, minHeight: 0, position: 'relative' }}
      >
        {/* Offscreen measurer (pre-render height calc) */}
        <Box
          ref={measurerHostRef}
          sx={{
            position: 'absolute',
            visibility: 'hidden',
            pointerEvents: 'none',
            left: 0,
            top: 0,
            zIndex: -1,
          }}
        />

        {/* Skeleton while debounce is active */}
        {isSearching ? (
          <Box sx={{ px: 0.5 }}>
            {[...Array(6)].map((_, i) => (
              <Skeleton
                key={i}
                variant='rectangular'
                height={40}
                sx={{ mb: 1, borderRadius: 1 }}
              />
            ))}
          </Box>
        ) : (
          <List
            rowCount={filteredRoutes.length}
            rowProps={{
              routes: filteredRoutes,
              selectedRoutes,
              onToggle: handleToggle,
            }}
            rowComponent={RowComponent}
            rowHeight={rowHeight}
          />
        )}
      </Box>
    </Box>
  );
}
