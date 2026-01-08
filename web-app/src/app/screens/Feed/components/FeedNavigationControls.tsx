import { Button, Grid, Typography } from '@mui/material';
import { ChevronLeft } from '@mui/icons-material';
import { getTranslations } from 'next-intl/server';
import { headers } from 'next/headers';

type Props = {
  feedDataType: string;
  feedId: string;
};

export default async function FeedNavigationControls({
  feedDataType,
  feedId,
}: Props) {
  const t = await getTranslations('common');
  const headersList = await headers();
  const referer = headersList.get('referer') ?? '/feeds';

  return (
    <Grid container spacing={3} alignItems='flex-end'>
      <Button
        sx={{ py: 0 }}
        size='large'
        startIcon={<ChevronLeft />}
        color={'inherit'}
        component={'a'}
        href={referer}
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
