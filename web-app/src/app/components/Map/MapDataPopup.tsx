import { Popup } from 'react-map-gl/maplibre';
import {
  getRouteTypeTranslatedName,
  getStopByLocationTypeOrDefault,
  renderLocationTypeIcon,
  renderRouteTypeIcon,
} from '../../constants/RouteTypes';
import { Box, Link, Typography, useTheme } from '@mui/material';
import AccessibleIcon from '@mui/icons-material/Accessible';
import { useTranslations } from 'next-intl';

interface MapDataPopupProps {
  mapClickRouteData: Record<string, string> | null;
  mapClickStopData: Record<string, string> | null;
  onPopupClose: () => void;
}

export const MapDataPopup = (
  props: React.PropsWithChildren<MapDataPopupProps>,
): React.ReactElement => {
  const { mapClickRouteData, mapClickStopData, onPopupClose } = props;
  const theme = useTheme();
  const t = useTranslations('feeds');
  const tCommon = useTranslations('common');

  function getGradientBorder(colorString: string): string {
    try {
      const colors: string[] = JSON.parse(colorString);

      if (!Array.isArray(colors) || colors.length === 0) {
        return 'none';
      }

      const gradient = `linear-gradient(to right, ${colors
        .map((c) => `#${c}`)
        .join(', ')})`;

      // Using border-image for gradient border
      return `6px solid transparent; border-image: ${gradient} 1;`;
    } catch {
      return 'none';
    }
  }

  return (
    <>
      {mapClickRouteData != null &&
        !Number.isNaN(Number(mapClickRouteData.longitude)) &&
        !Number.isNaN(Number(mapClickRouteData.latitude)) && (
          <Popup
            longitude={Number(mapClickRouteData.longitude)}
            latitude={Number(mapClickRouteData.latitude)}
            anchor='bottom'
            onClose={onPopupClose}
            closeOnClick={true}
            style={{
              minWidth: '200px',
            }}
          >
            <Box
              sx={{
                p: 1,
                backgroundColor: '#' + mapClickRouteData.route_color,
                color: '#' + mapClickRouteData.route_text_color,
              }}
            >
              <Box display={'flex'} alignItems={'center'} gap={1} my={1}>
                {renderRouteTypeIcon(
                  mapClickRouteData.route_type,
                  mapClickRouteData.route_text_color,
                )}
                <Typography component={'p'} variant={'body2'}>
                  {getRouteTypeTranslatedName(
                    mapClickRouteData.route_type,
                    tCommon,
                  )}{' '}
                  <b style={{ marginLeft: '8px' }}>
                    {mapClickRouteData.route_id}
                  </b>
                </Typography>
              </Box>

              <Typography component={'h3'} variant={'body1'} fontWeight={600}>
                {mapClickRouteData.route_long_name}
              </Typography>

              <p>{mapClickRouteData.agency_name}</p>
            </Box>
          </Popup>
        )}
      {mapClickStopData != null &&
        !Number.isNaN(Number(mapClickStopData.longitude)) &&
        !Number.isNaN(Number(mapClickStopData.latitude)) && (
          <Popup
            longitude={Number(mapClickStopData.longitude)}
            latitude={Number(mapClickStopData.latitude)}
            anchor='bottom'
            onClose={onPopupClose}
            closeOnClick={true}
            style={{
              minWidth: '200px',
            }}
          >
            <Box
              sx={{
                p: 1,
                border: getGradientBorder(mapClickStopData.route_colors),
                backgroundColor: theme.palette.background.paper,
                color: theme.palette.text.primary,
              }}
            >
              <Box
                display={'flex'}
                alignItems={'center'}
                justifyContent={'space-between'}
                my={1}
              >
                <Box display={'flex'} alignItems={'flex-end'} gap={1}>
                  {renderLocationTypeIcon(
                    mapClickStopData.location_type,
                    theme.palette.text.primary,
                  )}
                  <Typography component={'p'} variant={'body2'}>
                    {
                      getStopByLocationTypeOrDefault(
                        mapClickStopData.location_type,
                      ).name
                    }{' '}
                    <b style={{ marginLeft: '8px' }}>
                      {mapClickStopData.stop_id}
                    </b>
                  </Typography>
                </Box>
                {mapClickStopData.wheelchair_boarding === '1' && (
                  <AccessibleIcon
                    sx={{
                      backgroundColor: theme.palette.error.main,
                      color: theme.palette.error.contrastText,
                      borderRadius: '3px',
                      p: '2px',
                    }}
                  ></AccessibleIcon>
                )}
              </Box>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                <Typography
                  component={'h3'}
                  variant={'body1'}
                  fontWeight={600}
                  sx={{ mb: 1 }}
                >
                  {mapClickStopData.stop_name}
                </Typography>

                {mapClickStopData.route_ids != null &&
                  mapClickStopData.route_ids.replace(/[[\]"\\]/g, ',').length >
                    0 && (
                    <Typography variant='body2'>
                      <span style={{ marginRight: '8px' }}>
                        {t('routeIds')}
                      </span>
                      <b>
                        {mapClickStopData.route_ids.replace(/[[\]"\\]/g, ' ')}
                      </b>
                    </Typography>
                  )}

                {mapClickStopData.stop_code != null &&
                  mapClickStopData.stop_code.trim().length > 0 && (
                    <Typography variant='body2'>
                      <span style={{ marginRight: '8px' }}>
                        {t('stopCode')}
                      </span>
                      <b>{mapClickStopData.stop_code}</b>
                    </Typography>
                  )}
                {mapClickStopData.stop_url != null &&
                  mapClickStopData.stop_url.trim().length > 0 && (
                    <Link
                      href={mapClickStopData.stop_url}
                      underline='hover'
                      target='_blank'
                      rel='noreferrer'
                      variant={'body2'}
                      sx={{ mt: 1 }}
                    >
                      {t('viewStopInfo')}
                    </Link>
                  )}
              </Box>
            </Box>
          </Popup>
        )}
    </>
  );
};
