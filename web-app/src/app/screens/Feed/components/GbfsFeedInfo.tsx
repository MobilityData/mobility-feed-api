import * as React from 'react';
import { ContentBox } from '../../../components/ContentBox';
import { Box, Typography, useTheme, Link } from '@mui/material';
import { type GBFSFeedType } from '../../../services/feeds/utils';
import { useTranslation } from 'react-i18next';

import PublicIcon from '@mui/icons-material/Public';
import LinkIcon from '@mui/icons-material/Link';
import DatasetIcon from '@mui/icons-material/Dataset';
import Locations from '../../../components/Locations';
import SettingsIcon from '@mui/icons-material/Settings';
import StoreIcon from '@mui/icons-material/Store';
import FeedAuthenticationSummaryInfo from './FeedAuthenticationSummaryInfo';
import { boxElementStyle, StyledTitleContainer } from '../Feed.styles';

export interface GbfsFeedInfoProps {
  feed: GBFSFeedType;
  autoDiscoveryUrl?: string;
}

export default function GbfsFeedInfo({
  feed,
  autoDiscoveryUrl,
}: GbfsFeedInfoProps): React.ReactElement {
  const { t } = useTranslation('feeds');
  const theme = useTheme();

  return (
    <ContentBox
      title={'Feed Info'}
      outlineColor={theme.palette.primary.dark}
      padding={2}
    >
      <Box sx={boxElementStyle}>
        <StyledTitleContainer>
          <PublicIcon></PublicIcon>
          <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
            {t('locations')}
          </Typography>
        </StyledTitleContainer>
        <Box data-testid='location'>
          {feed?.locations != null && <Locations locations={feed?.locations} />}
        </Box>
      </Box>

      <Box sx={{ ...boxElementStyle, mt: 0 }}>
        <StyledTitleContainer sx={{ mt: 0 }}>
          <StoreIcon></StoreIcon>
          <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
            {t('producer')}
          </Typography>
        </StyledTitleContainer>
        <Link
          href={feed?.provider_url}
          variant='body1'
          target='_blank'
          rel='noreferrer'
        >
          {feed?.provider}
        </Link>
      </Box>

      {autoDiscoveryUrl != undefined && (
        <Box sx={boxElementStyle}>
          <StyledTitleContainer>
            <LinkIcon></LinkIcon>
            <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
              {t('gbfs:autoDiscoveryUrl')}
            </Typography>
          </StyledTitleContainer>
          <Link
            href={autoDiscoveryUrl}
            variant='body1'
            target='_blank'
            rel='noreferrer'
            sx={{ wordWrap: 'break-word' }}
          >
            {autoDiscoveryUrl}
          </Link>
        </Box>
      )}

      <Box sx={boxElementStyle}>
        <StyledTitleContainer>
          <SettingsIcon></SettingsIcon>
          <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
            System ID
          </Typography>
        </StyledTitleContainer>
        <Typography variant='body1'>{feed?.system_id}</Typography>
      </Box>

      <Box sx={boxElementStyle}>
        <StyledTitleContainer>
          <DatasetIcon></DatasetIcon>
          <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
            {t('dataType')}
          </Typography>
        </StyledTitleContainer>
        <Typography variant='body1'>GBFS</Typography>
      </Box>

      <FeedAuthenticationSummaryInfo feed={feed} />
    </ContentBox>
  );
}
