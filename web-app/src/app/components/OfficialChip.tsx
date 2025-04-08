import { Chip, Tooltip } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { verificationBadgeStyle } from '../styles/VerificationBadge.styles';
import VerifiedIcon from '@mui/icons-material/Verified';

export default function OfficialChip(): React.ReactElement {
  const { t } = useTranslation('feeds');
  return (
    <>
      <Tooltip title={t('officialFeedTooltip')} placement='top'>
        <Chip
          sx={verificationBadgeStyle}
          icon={<VerifiedIcon sx={{ fill: 'white' }}></VerifiedIcon>}
          label={t('officialFeed')}
        ></Chip>
      </Tooltip>
    </>
  );
}
