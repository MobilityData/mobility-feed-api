import * as React from 'react';
import 'leaflet/dist/leaflet.css';
import { Box, Typography } from '@mui/material';
import SubwayIcon from '@mui/icons-material/Subway';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';

export interface MapElement {
  isStop: boolean;
  routeType?: number;
  name: string;
  routeColor?: string;
  routeId?: string;
}

export interface MapElementProps {
  mapElements: MapElement[];
}

export const MapElement = (
  props: React.PropsWithChildren<MapElementProps>,
): JSX.Element => {

    const formatSet = new Set();
    const formattedElements: MapElement[] = [];
    // fE2 is not being used - to be completed
    const fE2: {[key: string]: MapElement[]}= {
        ['stops']: [],
        ['routes']: []
    }
    props.mapElements.forEach((element) => { 
        if(!formatSet.has(element.name)) {
            formattedElements.push(element)
            if(element.isStop) {
                fE2['stops'].push(element)
            } else {
                fE2['routes'].push(element)
            }
        }
        formatSet.add(element.name)
    });

    

  return (
    <Box
      sx={{
        position: 'absolute',
        top: '10px',
        left: '10px',
        zIndex: 1000,
      }}
    >
      {formattedElements.map((element, index) => {
        return (
          <Box
            sx={{
              background: 'white',
              borderRadius: '10px',
              boxShadow: '1px 1px 5px 1px rgba(0,0,0,0.2)',
              padding: '10px',
              my: 2,
              overflow: 'hidden',
              width: '250px',
            }}
          >
            <Typography variant='body1' sx={{mb: 1, fontSize: '12px'}}>{element.isStop ? "Stop" :"Route"}</Typography>
            {element.isStop ? (
              <Typography
                gutterBottom
                sx={{ color: 'text.secondary', fontSize: 14 }}
              >
                {element.name}
              </Typography>
            ) : (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: '#' + element.routeColor }}>
                {element.routeType == 1 ? (
                  <SubwayIcon
                    sx={{
                      color: element.routeColor,
                      fontSize: 20,
                    }}
                  />
                ) : (
                  <DirectionsBusIcon
                    sx={{
                      color: element.routeColor,
                      fontSize: 20,
                    }}
                  />
                )}
                <Typography
                  gutterBottom
                  sx={{ color: 'inherit', fontSize: 14, m: 0 }}
                >
                  {element.routeId} - {element.name}
                </Typography>
              </Box>
            )}
          </Box>
        );
      })}
    </Box>
  );
};