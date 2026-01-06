'use client';

import { Button, Grid, Typography } from '@mui/material';
import { ChevronLeft } from '@mui/icons-material';
import { useRouter } from 'next/navigation';
import { useTranslation } from 'react-i18next';

type Props = {
  feedDataType: string;
  feedId: string;
};

export default function FeedNavigationControls({
  feedDataType,
  feedId,
}: Props) {
  const router = useRouter();
  const { t } = useTranslation(['common', 'feeds']); // Ensure namespaces are loaded

  return (
    <Grid container size={12} spacing={3} alignItems={'end'}>
      <Button
        sx={{ py: 0 }}
        size='large'
        startIcon={<ChevronLeft />}
        color={'inherit'}
        onClick={() => {
          router.back();
        }}
      >
        {t('common:back')}
      </Button>

      <Grid>
        <Typography
          sx={{
            a: {
              textDecoration: 'none',
            },
          }}
        >
          <Button variant='text' href='/feeds' className='inline'>
            {t('common:feeds')}
          </Button>
          /
          <Button
            variant='text'
            href={`/feeds?${feedDataType}=true`}
            className='inline'
          >
            {t(`common:${feedDataType}`)}
          </Button>
          / {feedDataType === 'gbfs' ? feedId?.replace('gbfs-', '') : feedId}
        </Typography>
      </Grid>
    </Grid>
  );
}
