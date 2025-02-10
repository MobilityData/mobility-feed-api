/* eslint-disable */

import * as React from 'react';
import ListSubheader from '@mui/material/ListSubheader';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Collapse from '@mui/material/Collapse';
import InboxIcon from '@mui/icons-material/MoveToInbox';
import DraftsIcon from '@mui/icons-material/Drafts';
import SendIcon from '@mui/icons-material/Send';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import StarBorder from '@mui/icons-material/StarBorder';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import { Typography } from '@mui/material';

export interface RouteAvailabilitiesProps {}

const sampleRoutes = [
  {
    routeId: 1,
    routeName: 'Orange Line',
    color: '#FFA500',
    startDate: '2021-01-01',
    endDate: '2021-01-31',
    monday: true,
    tuesday: true,
    wednesday: true,
    thursday: true,
    friday: true,
    saturday: false,
    sunday: false,
    opened: false, // added
  },
  {
    routeId: 2,
    routeName: 'Blue Line',
    color: '#FFA500',
    startDate: '2021-01-01',
    endDate: '2021-01-31',
    monday: true,
    tuesday: true,
    wednesday: true,
    thursday: true,
    friday: true,
    saturday: false,
    sunday: false,
    opened: false, // added
  },
  {
    routeId: 3,
    routeName: 'Green Line',
    color: '#FFA500',
    startDate: '2021-01-01',
    endDate: '2021-01-31',
    monday: true,
    tuesday: true,
    wednesday: true,
    thursday: true,
    friday: true,
    saturday: false,
    sunday: false,
    opened: false, // added
  },
];

export const RouteAvailabilities = (
  props: React.PropsWithChildren<RouteAvailabilitiesProps>,
): JSX.Element => {
  const [routeData, setRouteData] = React.useState(sampleRoutes);

  const handleClick = (id: number, newOpenValue: boolean) => {
    const routeIndex = routeData.findIndex((rd) => id === rd.routeId);
    if (routeIndex != -1) {
      const newRouteData = routeData.slice();
      newRouteData[routeIndex].opened = newOpenValue;
      setRouteData(newRouteData);
    }
  };
  return (
    <List
      sx={{ width: '100%', maxWidth: 750, bgcolor: 'white', mx: 'auto' }}
      component='nav'
      aria-labelledby='nested-list-subheader'
      subheader={
        <ListSubheader component='div' id='nested-list-subheader'>
          STM Routes
        </ListSubheader>
      }
    >
      {sampleRoutes.map((route) => {
        return (
          <>
            <ListItemButton
                key={route.routeId}
                onClick={() => handleClick(route.routeId, !route.opened)}
            >
              <ListItemIcon>
                <InboxIcon />
              </ListItemIcon>
              <ListItemText primary={route.routeName} />
              {route.opened ? <ExpandLess /> : <ExpandMore />}
            </ListItemButton>
            <Collapse in={route.opened} timeout='auto' unmountOnExit sx={{mb: 2, p: 2, borderBottom: '1px solid #ccc'}}>
            <Typography variant='body2' sx={{mb: 2}}>Service Date: {route.startDate} - {route.endDate}</Typography>
              <Stack direction='row' spacing={1}>
                <Chip label='Monday' variant={route.monday ? 'filled' : 'outlined'} />
                <Chip label='Tuesday' variant={route.tuesday ? 'filled' : 'outlined'} />
                <Chip label='Wednesday' variant={route.wednesday ? 'filled' : 'outlined'} />
                <Chip label='Thursday' variant={route.thursday ? 'filled' : 'outlined'} />
                <Chip label='Friday' variant={route.friday ? 'filled' : 'outlined'} />
                <Chip label='Saturday' variant={route.saturday ? 'filled' : 'outlined'} />
                <Chip label='Sunday' variant={route.sunday ? 'filled' : 'outlined'} />
              </Stack>
            </Collapse>
          </>
        );
      })}
    </List>
  );
};
