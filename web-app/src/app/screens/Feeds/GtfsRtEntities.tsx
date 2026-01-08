import { Box, Chip, type SxProps, Tooltip, colors } from '@mui/material';
import * as React from 'react';

import UpdateIcon from '@mui/icons-material/Update';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import { useTranslations } from 'next-intl';

type GtfsRtEntitySelection = 'vp' | 'tu' | 'sa';

interface GtfsRtEntitiesProps {
  entities: GtfsRtEntitySelection[] | undefined;
  includeName?: boolean;
}

const iconStyle = (textColor: string): SxProps => ({
  color: textColor,
  borderRadius: '50%',
  display: 'block',
  '&.MuiSvgIcon-root.MuiChip-icon': {
    color: textColor,
  },
});

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
  const t = useTranslations('common');
  const entityData = {
    vp: {
      icon: (
        <LocationOnIcon
          sx={{ ...iconStyle('white'), background: colors.blue[700] }}
        />
      ),
      title: t('gtfsRealtimeEntities.vehiclePositions'),
      color: colors.blue[700],
      textColor: 'white',
    },
    tu: {
      icon: (
        <UpdateIcon
          sx={{ ...iconStyle(colors.blue[900]), background: colors.blue[200] }}
        />
      ),
      title: t('gtfsRealtimeEntities.tripUpdates'),
      color: colors.blue[200],
      textColor: colors.blue[900],
    },
    sa: {
      icon: (
        <WarningAmberIcon
          sx={{ ...iconStyle('white'), background: colors.blue[900] }}
        />
      ),
      title: t('gtfsRealtimeEntities.serviceAlerts'),
      color: colors.blue[900],
      textColor: 'white',
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
                  fontWeight: 'bold',
                  color: entityData[entity].textColor,
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
