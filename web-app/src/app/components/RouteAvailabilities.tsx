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
import {
  Box,
  InputAdornment,
  ListItem,
  TextField,
  Typography,
  useTheme,
} from '@mui/material';
import sampleRoutes from './sample-route-output.json';
import SubwayIcon from '@mui/icons-material/Subway';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import { Search } from '@mui/icons-material';
import CancelIcon from '@mui/icons-material/Cancel';

export interface RouteAvailabilitiesProps {}

interface Route {
  routeId: string;
  routeName: string;
  color: string;
  textColor: string;
  routeType: string;
  startDate: string;
  endDate: string;
  monday: boolean;
  tuesday: boolean;
  wednesday: boolean;
  thursday: boolean;
  friday: boolean;
  saturday: boolean;
  sunday: boolean;
  opened: boolean;
}

function formatDate(yyyymmdd: string): string {
  const year = yyyymmdd.substring(0, 4);
  const month = yyyymmdd.substring(4, 6);
  const day = yyyymmdd.substring(6, 8);

  const date = new Date(`${year}-${month}-${day}`);
  
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

// This is a function available by default in Typescript 5.2
function groupBy<T, K extends string | number | symbol>(
  array: T[],
  keyFn: (item: T) => K,
): Record<K, T[]> {
  return array.reduce(
    (acc, item) => {
      const key = keyFn(item);
      (acc[key] ||= []).push(item);
      return acc;
    },
    {} as Record<K, T[]>,
  );
}

// const sampleRoutes = [
//   {
//     routeId: 1,
//     routeName: 'Orange Line',
//     color: '#FFA500',
//     startDate: '2021-01-01',
//     endDate: '2021-01-31',
//     monday: true,
//     tuesday: true,
//     wednesday: true,
//     thursday: true,
//     friday: true,
//     saturday: false,
//     sunday: false,
//     opened: false, // added
//   },
//   {
//     routeId: 2,
//     routeName: 'Blue Line',
//     color: '#FFA500',
//     startDate: '2021-01-01',
//     endDate: '2021-01-31',
//     monday: true,
//     tuesday: true,
//     wednesday: true,
//     thursday: true,
//     friday: true,
//     saturday: false,
//     sunday: false,
//     opened: false, // added
//   },
//   {
//     routeId: 3,
//     routeName: 'Green Line',
//     color: '#FFA500',
//     startDate: '2021-01-01',
//     endDate: '2021-01-31',
//     monday: true,
//     tuesday: true,
//     wednesday: true,
//     thursday: true,
//     friday: true,
//     saturday: false,
//     sunday: false,
//     opened: false, // added
//   },
// ];

export const RouteAvailabilities = (
  props: React.PropsWithChildren<RouteAvailabilitiesProps>,
): JSX.Element => {
  const theme = useTheme();
  const [searchInputValue, setSearchInputValue] = React.useState('');
  const [routeData, setRouteData] = React.useState<Route[]>(
    sampleRoutes.map((route) => ({ ...route, opened: false })),
  );

  const handleClick = (id: string, newOpenValue: boolean) => {
    const routeIndex = routeData.findIndex((rd) => id === rd.routeId);
    if (routeIndex != -1) {
      const newRouteData = routeData.slice();
      newRouteData[routeIndex].opened = newOpenValue;
      setRouteData(newRouteData);
    }
  };

  const groupedRoutes = groupBy(routeData, ({ routeType }) => routeType);

  // Virtual list optimization
  // https://mui.com/material-ui/react-list/?srsltid=AfmBOorUcm-bOPZA1txx6vrW21aNliqrJwsFNt-c7WUF2lkmMCtwd3u2
  return (
    <>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
        }}
      >
        <TextField
          sx={{
            width: '100%',
            maxWidth: 750,
            backgroundColor: 'white',
            mb: 2,
            mt: 2,
            fieldset: {
              borderColor: theme.palette.primary.main,
            },
          }}
          value={searchInputValue}
          onChange={(e) => {
            setSearchInputValue(e.target.value);
          }}
          placeholder='Search for a route'
          InputProps={{
            startAdornment: (
              <InputAdornment position={'start'}>
                <Search />
              </InputAdornment>
            ),
            endAdornment: (
              <InputAdornment position={'end'} sx={{ cursor: 'pointer' }}>
                <CancelIcon
                  onClick={() => {
                    setSearchInputValue('');
                  }}
                />
              </InputAdornment>
            ),
          }}
        />
      </Box>

      {Object.keys(groupedRoutes).map((routeType) => (
        <List
          key={routeType}
          dense={true}
          sx={{ width: '100%', maxWidth: 750, bgcolor: 'white', mx: 'auto' }}
          subheader={
            <ListSubheader
              sx={{ display: 'flex', alignItems: 'center', bgcolor: 'white' }}
            >
              <ListItemIcon>
                {routeType === '1' ? <SubwayIcon /> : <DirectionsBusIcon />}
              </ListItemIcon>
              {routeType === '1' ? 'Metro' : 'Bus'}
            </ListSubheader>
          }
        >
          {(groupedRoutes[routeType] ?? [])
            .filter(
              (routePre) =>
                routePre.routeId
                  .toLowerCase()
                  .includes(searchInputValue.toLowerCase()) ||
                routePre.routeName
                  .toLowerCase()
                  .includes(searchInputValue.toLowerCase()),
            )
            .sort((a, b) => Number(a.routeId) - Number(b.routeId))
            .map((route) => {
              return (
                <>
                  <ListItemButton
                    key={route.routeId}
                    onClick={() => handleClick(route.routeId, !route.opened)}
                  >
                    <Box
                      sx={{
                        background: route.color,
                        color: route.textColor,
                        width: 30,
                        height: 30,
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        textAlign: 'center',
                        mr: 2,
                      }}
                    >
                      <ListItemText primary={`${route.routeId}`} />
                    </Box>
                    <ListItemText primary={`${route.routeName}`} />
                    {route.opened ? <ExpandLess /> : <ExpandMore />}
                  </ListItemButton>
                  <Collapse
                    in={route.opened}
                    timeout='auto'
                    unmountOnExit
                  >
                    <Box sx={{ mb: 2, p: 2, borderBottom: '1px solid #ccc', pt: 1 }}>
                    <Typography variant='body2' sx={{ mb: 2 }}>
                      <Box component={'span'} sx={{fontWeight: 'bold', mr: 2}}>Service Date</Box> {formatDate(route.startDate)} <Box component={'span'} sx={{mx:1}}>-</Box>{formatDate(route.endDate)}
                    </Typography>
                    <Stack direction='row' spacing={1}>
                      <Chip
                        label='Monday'
                        variant={route.monday ? 'filled' : 'outlined'}
                        color={route.monday ? 'primary' : 'default'}
                      />
                      <Chip
                        label='Tuesday'
                        variant={route.tuesday ? 'filled' : 'outlined'}
                        color={route.tuesday ? 'primary' : 'default'}
                      />
                      <Chip
                        label='Wednesday'
                        variant={route.wednesday ? 'filled' : 'outlined'}
                        color={route.wednesday ? 'primary' : 'default'}
                      />
                      <Chip
                        label='Thursday'
                        variant={route.thursday ? 'filled' : 'outlined'}
                        color={route.thursday ? 'primary' : 'default'}
                      />
                      <Chip
                        label='Friday'
                        variant={route.friday ? 'filled' : 'outlined'}
                        color={route.friday ? 'primary' : 'default'}
                      />
                      <Chip
                        label='Saturday'
                        variant={route.saturday ? 'filled' : 'outlined'}
                        color={route.saturday ? 'primary' : 'default'}
                      />
                      <Chip
                        label='Sunday'
                        variant={route.sunday ? 'filled' : 'outlined'}
                        color={route.sunday ? 'primary' : 'default'}
                      />
                    </Stack>
                    </Box>
                    
                  </Collapse>
                </>
              );
            })}
        </List>
      ))}
    </>
  );
};
