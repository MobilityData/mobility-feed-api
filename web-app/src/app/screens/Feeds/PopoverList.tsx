import { Popper, Box, Typography, useTheme } from '@mui/material';
import { useTranslations } from 'next-intl';

interface PopoverListProps {
  popoverData: string[];
  anchorEl: HTMLElement | null;
  title: string;
}

export default function PopoverList({
  popoverData,
  anchorEl,
  title,
}: PopoverListProps): React.ReactElement {
  const theme = useTheme();
  const t = useTranslations('feeds');
  return (
    <Popper
      open={popoverData !== undefined}
      anchorEl={anchorEl}
      placement='top'
      sx={{
        backgroundColor: theme.palette.background.paper,
        boxShadow: theme.palette.boxShadow,
        zIndex: 1000,
      }}
    >
      <Box
        sx={{
          padding: 2,
          pb: 0,
          width: '400px',
          maxWidth: '100%',
        }}
      >
        <Typography variant='h6' sx={{ p: 0, fontSize: '16px' }}>
          {title}
        </Typography>
      </Box>

      <Box sx={{ fontSize: '14px', display: 'inline' }}>
        <ul>
          {popoverData.slice(0, 10).map((provider, index) => (
            <li key={index}>{provider}</li>
          ))}
          {popoverData.length > 10 && (
            <li>
              <b>
                {t('seeDetailPageProviders', {
                  providersCount: popoverData.length - 10,
                })}
              </b>
            </li>
          )}
        </ul>
      </Box>
    </Popper>
  );
}
