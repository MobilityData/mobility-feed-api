'use client';

import { Chip, Tooltip } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { verificationBadgeStyle } from '../styles/VerificationBadge.styles';
import VerifiedIcon from '@mui/icons-material/Verified';

interface OfficialChipProps {
  isLongDisplay?: boolean;
}

export default function OfficialChip({
  isLongDisplay = true,
}: OfficialChipProps): React.ReactElement {
  const { t } = useTranslation('feeds');
  return (
    <>
      {isLongDisplay ? (
        <Tooltip title={t('officialFeedTooltip')} placement='top'>
          <Chip
            sx={verificationBadgeStyle}
            icon={<VerifiedIcon sx={{ fill: 'white' }}></VerifiedIcon>}
            label={t('officialFeed')}
          ></Chip>
        </Tooltip>
      ) : (
        <Tooltip title={t('officialFeedTooltipShort')} placement='top'>
          <VerifiedIcon
            sx={(theme) => ({
              display: 'block',
              borderRadius: '50%',
              padding: '0.1rem',
              ml: 0,
              mr: 2,
              ...verificationBadgeStyle(theme),
            })}
          ></VerifiedIcon>
        </Tooltip>
      )}
    </>
  );
}
