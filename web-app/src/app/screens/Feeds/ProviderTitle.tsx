import { Box, Chip, useTheme } from '@mui/material';
import {
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';
import { useTranslations } from 'next-intl';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

interface ProviderTitleProps {
  feed: GTFSFeedType | GTFSRTFeedType;
  setPopoverData: (data: string[] | undefined) => void;
  setAnchorEl: (el: HTMLElement | null) => void;
}

export default function ProviderTitle({
  feed,
  setPopoverData,
  setAnchorEl,
}: ProviderTitleProps): React.ReactElement {
  const theme = useTheme();
  const t = useTranslations('feeds');
  const providers =
    feed?.provider
      ?.split(',')
      .filter((x) => x)
      .sort() ?? [];
  const displayName = providers[0];
  let manyProviders: React.ReactElement | undefined;
  if (providers.length > 1) {
    manyProviders = (
      <span
        style={{
          fontStyle: 'italic',
          fontSize: '14px',
          fontWeight: 'bold',
          color: theme.palette.primary.main,
          padding: 2,
        }}
        onMouseEnter={(event) => {
          setPopoverData(providers);
          setAnchorEl(event.currentTarget);
        }}
        onMouseLeave={() => {
          setPopoverData(undefined);
          setAnchorEl(null);
        }}
      >
        +&nbsp;{providers.length - 1}
      </span>
    );
  }
  return (
    <>
      {displayName} {manyProviders}
      {feed?.status === 'deprecated' && (
        <Box sx={{ mt: '5px' }}>
          <Chip
            label={t('deprecated')}
            icon={<ErrorOutlineIcon />}
            color='error'
            size='small'
            variant='outlined'
          />
        </Box>
      )}
    </>
  );
}
