import { Typography, Box, Container, CssBaseline } from '@mui/material';
import { theme } from '../Theme';

export default function FeedSubmitted(): React.ReactElement {
  return (
    <Container component='main' sx={{ my: 0, mx: 'auto' }} maxWidth='lg'>
      <CssBaseline />
      <Typography
        data-cy='feedSubmitSuccess'
        component='h1'
        variant='h4'
        sx={{
          mt: 10,
          mb: 4,
          mx: 2,
          color: theme.palette.primary.main,
          fontWeight: 'bold',
        }}
      >
        🚀 Your feed has been submitted!
      </Typography>
      <Box sx={{ display: 'flex', flexDirection: 'row', p: 2 }}>
        <img
          src='/assets/rocket.gif'
          alt='rocket'
          style={{ width: '300px', height: '300px', marginRight: '60px' }}
        />
        <Box sx={{ maxWidth: '615px', justifyContent: 'center' }}>
          <Typography variant='body1' sx={{ mb: 2, fontSize: '20px' }}>
            Thank you for your precious contribution to the Mobility Database!
            Your feed will be available on the website within the next 2 weeks.
          </Typography>
          <Typography variant='body1' sx={{ mb: 2, fontSize: '20px' }}>
            You&rsquo;ll also be included in our {/* TODO: implement ancor */}
            <a href='/contribute-faq#contributors-list'>Contributors List.</a>
          </Typography>
          <Typography variant='body1' sx={{ mb: 2, fontSize: '20px' }}>
            If you have any questions or feedback,{' '}
            <a href='mailto:api@mobilitydata.org'>please contact us.</a>
          </Typography>
        </Box>
      </Box>
    </Container>
  );
}
