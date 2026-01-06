'use client';

import { Button } from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { useTranslation } from 'react-i18next';

export default function ClientQualityReportButton({ url }: { url: string }) {
  const { t } = useTranslation('feeds'); // Assumes i18n is available client-side

  const handleOpenFullQualityReportClick = async (): Promise<void> => {
    const ReactGA = (await import('react-ga4')).default;
    ReactGA.event({
      category: 'engagement',
      action: 'open_full_quality_report',
      label: 'Open Full Quality Report',
    });
  };

  return (
    <Button
      variant='outlined'
      disableElevation
      href={url}
      target='_blank'
      rel='noreferrer nofollow'
      endIcon={<OpenInNewIcon />}
      onClick={handleOpenFullQualityReportClick}
    >
      {t('openFullQualityReport')}
    </Button>
  );
}
