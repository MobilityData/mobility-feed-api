import { Box, Chip, type SxProps, Tooltip, colors } from '@mui/material';
import * as React from 'react';

import UpdateIcon from '@mui/icons-material/Update';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import { useTranslation } from 'react-i18next';

type GtfsRtEntitySelection = 'vp' | 'tu' | 'sa';

interface GtfsRtEntitiesProps {
  entities: GtfsRtEntitySelection[] | undefined;
  includeName?: boolean;
}

const iconStyle: SxProps = {
  color: 'white',
  borderRadius: '50%',
  display: 'block',
  '&.MuiSvgIcon-root.MuiChip-icon': {
    color: 'white',
  },
};

const longContainerStyle: SxProps = {
  flexDirection: 'row',
  justifyContent: 'flex-start',
  gap: 1,
  display: 'flex',
};

const shortContainerStyle: SxProps = {
  flexDirection: 'column',
  justifyContent: 'center',
  gap: '2px',
  display: 'flex',
  svg: {
    p: '3px',
  },
};

export default function GtfsRtEntities({
  entities,
  includeName = false,
}: GtfsRtEntitiesProps): React.ReactElement {
  const { t } = useTranslation('common');
  const entityData = {
    vp: {
      icon: (
        <LocationOnIcon sx={{ ...iconStyle, background: colors.blue[600] }} />
      ),
      title: t('gtfsRealtimeEntities.vehiclePositions'),
      color: colors.blue[600],
    },
    tu: {
      icon: <UpdateIcon sx={{ ...iconStyle, background: colors.blue[300] }} />,
      title: t('gtfsRealtimeEntities.tripUpdates'),
      color: colors.blue[300],
    },
    sa: {
      icon: (
        <WarningAmberIcon sx={{ ...iconStyle, background: colors.blue[900] }} />
      ),
      title: t('gtfsRealtimeEntities.serviceAlerts'),
      color: colors.blue[900],
    },
  };

  if (entities == undefined) {
    return <></>;
  }
  const sortedEntities = [...entities].sort();
  return (
    <Box sx={includeName ? longContainerStyle : shortContainerStyle}>
      {sortedEntities.map((entity) => {
        return (
          <Box key={entity}>
            {includeName ? (
              <Chip
                size='small'
                label={entityData[entity].title}
                variant='filled'
                icon={entityData[entity].icon}
                sx={{
                  width: 'fit-content',
                  backgroundColor: entityData[entity].color,
                  borderColor: entityData[entity].color,
                  color: 'white',
                }}
              ></Chip>
            ) : (
              <Tooltip title={entityData[entity].title} placement='top'>
                {entityData[entity].icon}
              </Tooltip>
            )}
          </Box>
        );
      })}
    </Box>
  );
}
