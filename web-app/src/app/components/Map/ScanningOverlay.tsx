import {
  Box,
  Button,
  CircularProgress,
  LinearProgress,
  Typography,
  useTheme,
} from '@mui/material';
import { useTranslations } from 'next-intl';

interface ScanningOverlayProps {
  totalTiles: number;
  scannedTiles: number;
  scanRowsCols: {
    rows: number;
    cols: number;
  } | null;
  handleCancelScan: () => void;
  cancelRequestRef: React.MutableRefObject<boolean>;
}

export const ScanningOverlay = (
  props: React.PropsWithChildren<ScanningOverlayProps>,
): JSX.Element => {
  const {
    totalTiles,
    scannedTiles,
    scanRowsCols,
    handleCancelScan,
    cancelRequestRef,
  } = props;
  const theme = useTheme();
  const t = useTranslations('feeds');
  const progressPct =
    totalTiles > 0
      ? Math.min(100, Math.round((scannedTiles / totalTiles) * 100))
      : 0;
  const isLarge = totalTiles >= 80;
  const rowsColsText =
    scanRowsCols != null
      ? `${scanRowsCols.rows} rows × ${scanRowsCols.cols} cols`
      : undefined;
  return (
    <Box
      role='status'
      aria-live='polite'
      sx={{
        position: 'absolute',
        inset: 0,
        zIndex: 1200,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backdropFilter: 'blur(2px)',
        background:
          'linear-gradient(180deg, rgba(255,255,255,0.65) 0%, rgba(255,255,255,0.55) 100%)',
      }}
    >
      <Box
        sx={{
          width: 420,
          maxWidth: '90%',
          bgcolor: theme.palette.background.paper,
          borderRadius: '14px',
          boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
          border: `1px solid ${theme.palette.divider}`,
          p: 2.25,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.25,
            mb: 1,
          }}
        >
          <CircularProgress size={20} thickness={4} />
          <Typography variant='subtitle1' sx={{ fontWeight: 700 }}>
            {isLarge ? t('scanning.titleLarge') : t('scanning.title')}
          </Typography>
        </Box>

        <Typography
          variant='body2'
          sx={{ mb: 1, color: theme.palette.text.secondary }}
        >
          {isLarge ? t('scanning.bodyLarge') : t('scanning.body')}
        </Typography>

        {rowsColsText != null && (
          <Typography
            variant='caption'
            sx={{ display: 'block', mb: 1, opacity: 0.9 }}
          >
            {t('scanning.gridTile', {
              grid: rowsColsText,
              tile: Math.min(scannedTiles, totalTiles),
              total: totalTiles,
            })}
          </Typography>
        )}

        <LinearProgress
          variant='determinate'
          value={progressPct}
          sx={{
            height: 8,
            borderRadius: '999px',
            mb: 1,
          }}
        />

        <Typography
          variant='caption'
          sx={{ color: theme.palette.text.secondary }}
        >
          {t('scanning.percentComplete', { percent: progressPct })}
        </Typography>
        <Box sx={{ display: 'flex', flexDirection: 'row-reverse' }}>
          <Button
            size='small'
            variant='outlined'
            onClick={handleCancelScan}
            disabled={cancelRequestRef.current}
            aria-label={t('scanning.cancel')}
          >
            {t('scanning.cancel')}
          </Button>
        </Box>
      </Box>
    </Box>
  );
};
