'use client';

import { Button } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import { useTranslation } from 'react-i18next';

export default function ClientDownloadButton({ url }: { url: string }) {
  
  const { t } = useTranslation('feeds');

  const handleDownloadLatestClick = async (): Promise<void> => {
    const ReactGA = (await import('react-ga4')).default;
    ReactGA.event({
      category: 'engagement',
      action: 'download_latest_dataset',
      label: 'Download Latest Dataset',
    });
  };

  return (
    <Button
      disableElevation
      variant='contained'
      href={url}
      target='_blank'
      rel='noreferrer nofollow'
      id='download-latest-button'
      endIcon={<DownloadIcon />}
      onClick={handleDownloadLatestClick}
    >
      {t('downloadLatest')}
    </Button>
  );
}
