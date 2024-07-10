import { Box, type SxProps, Tooltip, colors } from '@mui/material';
import * as React from 'react';

import UpdateIcon from '@mui/icons-material/Update';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import { useTranslation } from 'react-i18next';

type GtfsRtEntitySelection = 'vp' | 'tu' | 'sa';

interface GtfsRtEntitiesProps {
  entities: GtfsRtEntitySelection[] | undefined;
}

const iconStyle: SxProps = {
  color: 'white',
  borderRadius: '50%',
  padding: '3px',
};

export default function GtfsRtEntities({
  entities,
}: GtfsRtEntitiesProps): React.ReactElement {
  const { t } = useTranslation('common');
  const entityData = {
    vp: {
      icon: (
        <LocationOnIcon sx={{ ...iconStyle, background: colors.blue[600] }} />
      ),
      title: t('gtfsRealtimeEntities.vehiclePositions'),
    },
    tu: {
      icon: <UpdateIcon sx={{ ...iconStyle, background: colors.blue[300] }} />,
      title: t('gtfsRealtimeEntities.tripUpdates'),
    },
    sa: {
      icon: (
        <WarningAmberIcon sx={{ ...iconStyle, background: colors.blue[900] }} />
      ),
      title: t('gtfsRealtimeEntities.serviceAlerts'),
    },
  };
  return (
    <Box
      sx={{
        display: 'flex',
        ml: 1,
        flexDirection: 'column',
        justifyContent: 'center',
        gap: '2px',
      }}
    >
      {entities?.map((entity) => {
        return (
          <Tooltip
            title={entityData[entity].title}
            placement='top'
            key={entity}
          >
            {entityData[entity].icon}
          </Tooltip>
        );
      })}
    </Box>
  );
}
