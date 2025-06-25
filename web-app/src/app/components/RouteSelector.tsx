import React, { useState, useMemo, useEffect } from 'react';
import {
  TextField,
  List,
  Checkbox,
  ListItemText,
  ListItemIcon,
  Typography,
  Box,
  ListItemButton,
} from '@mui/material';

interface RouteSelectorProps {
  routes: Array<any>; // Replace 'any' with a more specific type if available
  selectedRouteIds?: string[];
  onSelectionChange?: (selectedRoutes: string[]) => void;
}

export default function RouteSelector({
  routes,
  selectedRouteIds = [],
  onSelectionChange,
}: RouteSelectorProps) {
  const [search, setSearch] = useState('');
  const [selectedRoutes, setSelectedRoutes] =
    useState<string[]>(selectedRouteIds);

  const filteredRoutes = useMemo(() => {
    const searchLower = search.toLowerCase();
    return routes.filter(
      (route) =>
        route.routeName.toLowerCase().includes(searchLower) ||
        route.routeId.includes(searchLower),
    );
  }, [search, routes]);

  useEffect(() => {
    setSelectedRoutes([...selectedRouteIds]);
  }, [selectedRouteIds]);

  const handleToggle = (routeId: string) => {
    setSelectedRoutes((prev) => {
      const newSelection = prev.includes(routeId)
        ? prev.filter((id) => id !== routeId)
        : [...prev, routeId];

      onSelectionChange?.(newSelection);
      return newSelection;
    });
  };

  return (
    <Box
      sx={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        minHeight: '300px',
        overflowY: 'auto',
      }}
    >
      <Typography variant='subtitle2' sx={{ m: 0 }}>
        {filteredRoutes.length} route{filteredRoutes.length !== 1 ? 's' : ''}
      </Typography>
      <TextField
        fullWidth
        variant='outlined'
        size='small'
        placeholder='Search routes...'
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      <List dense sx={{ maxHeight: 'none', overflow: 'auto', flex: 1}}>
        {filteredRoutes
          .sort((a, b) => a.routeId - b.routeId)
          .map((route) => (
            <ListItemButton
              key={route.routeId}
              sx={{ pl: 0 }}
              onClick={() => handleToggle(route.routeId)}
              dense={true}
            >
              <ListItemIcon sx={{ minWidth: 34 }}>
                <Checkbox
                  edge='start'
                  checked={selectedRoutes.includes(route.routeId)}
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
                        backgroundColor: route.color || '#000',
                        borderRadius: '4px',
                        mr: 1,
                        border: '1px solid #999',
                      }}
                    />
                    <Typography variant={'inherit'} sx={{ flex: 1 }}>
                      {route.routeId} - {route.routeName}
                    </Typography>
                  </Box>
                }
              />
            </ListItemButton>
          ))}
      </List>
    </Box>
  );
}
