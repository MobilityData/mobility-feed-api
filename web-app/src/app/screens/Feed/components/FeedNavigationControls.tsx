'use client';

import { Button, Grid, Typography } from '@mui/material';
import { ChevronLeft } from '@mui/icons-material';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';

type Props = {
  feedDataType: string;
  feedId: string;
};

export default function FeedNavigationControls({
  feedDataType,
  feedId,
}: Props) {
  const router = useRouter();
  const t = useTranslations('common');

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
        {t('back')}
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
            {t('feeds')}
          </Button>
          /
          <Button
            variant='text'
            href={`/feeds?${feedDataType}=true`}
            className='inline'
          >
            {t(`${feedDataType}`)}
          </Button>
          / {feedDataType === 'gbfs' ? feedId?.replace('gbfs-', '') : feedId}
        </Typography>
      </Grid>
    </Grid>
  );
}
