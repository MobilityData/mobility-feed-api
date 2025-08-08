import React, { useState, useMemo } from 'react';
import {
  Drawer,
  TextField,
  List,
  ListItem,
  Checkbox,
  ListItemText,
  ListItemIcon,
  Typography,
  Box,
  Chip
} from '@mui/material';

interface RouteSelectorProps {
  routes: Array<any>; // Replace 'any' with a more specific type if available
  onSelectionChange?: (selectedRoutes: string[]) => void;
  open?: boolean;
}

export default function RouteSelector({ routes, onSelectionChange, open = true }: RouteSelectorProps) {
  const [search, setSearch] = useState('');
  const [selectedRoutes, setSelectedRoutes] = useState<string[]>([]);

  const filteredRoutes = useMemo(() => {
    const searchLower = search.toLowerCase();
    return routes.filter(route =>
      route.routeName.toLowerCase().includes(searchLower) ||
      route.routeId.includes(searchLower)
    );
  }, [search, routes]);

  const handleToggle = (routeId: string) => {
    setSelectedRoutes(prev => {
      const newSelection = prev.includes(routeId)
        ? prev.filter(id => id !== routeId)
        : [...prev, routeId];

      onSelectionChange?.(newSelection);
      return newSelection;
    });
  };

  return (
    <Drawer anchor="left" open={open} variant="persistent" sx={{ width: 300, flexShrink: 0 }}>
      <Box sx={{ p: 2, width: 300 }}>
        <Typography variant="h6" gutterBottom> Select Routes </Typography>
        <TextField
          fullWidth
          variant="outlined"
          size="small"
          placeholder="Search routes..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ mb: 2 }}
        />
        <List dense sx={{ maxHeight: '80vh', overflow: 'auto' }}>
          {filteredRoutes.map(route => (
            <ListItem key={route.routeId} button onClick={() => handleToggle(route.routeId)}>
              <ListItemIcon>
                <Checkbox
                  edge="start"
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
                        border: '1px solid #999'
                      }}
                    />
                    {route.routeName}
                  </Box>
                }
              />
            </ListItem>
          ))}
        </List>
      </Box>
    </Drawer>
  );
}
