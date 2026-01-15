'use client';

import { Button } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import { useTranslations } from 'next-intl';

export default function ClientDownloadButton({
  url,
}: {
  url: string;
}): JSX.Element {
  const t = useTranslations('feeds');

  const handleDownloadLatestClick = async (): Promise<void> => {
    // Lazy load react-ga4 to avoid loading it unnecessarily
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
      onClick={() => {
        void handleDownloadLatestClick();
      }}
    >
      {t('downloadLatest')}
    </Button>
  );
}
