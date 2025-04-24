import { Box, Button, Typography } from '@mui/material';
import {
  AllFeedType,
} from '../../../services/feeds/utils';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import LockIcon from '@mui/icons-material/Lock';
import { useTranslation } from 'react-i18next';
import { boxElementStyle, StyledTitleContainer } from '../Feed.styles';

interface FeedAuthenticationSummaryInfoProps {
  feed: AllFeedType;
}

export default function FeedAuthenticationSummaryInfo({
  feed,
}: FeedAuthenticationSummaryInfoProps): React.ReactElement {
  const { t } = useTranslation('feeds');

  const hasAuthenticationInfo =
    feed?.source_info?.authentication_info_url != undefined &&
    feed?.source_info.authentication_info_url.trim() !== '';
  return (
    <>
      {feed?.source_info?.authentication_type !== 0 && (
        <Box sx={boxElementStyle}>
          <StyledTitleContainer>
            <LockIcon></LockIcon>
            <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
              {t('authenticationType')}
            </Typography>
            <Typography data-testid='data-type'>
              {feed?.source_info?.authentication_type === 1 &&
                t('common:apiKey')}
              {feed?.source_info?.authentication_type === 2 &&
                t('common:httpHeader')}
            </Typography>
          </StyledTitleContainer>
        </Box>
      )}

      {hasAuthenticationInfo &&
        feed?.source_info?.authentication_info_url != undefined && (
          <Button
            disableElevation
            variant='outlined'
            href={feed?.source_info?.authentication_info_url}
            target='_blank'
            rel='noreferrer'
            sx={{ marginRight: 2 }}
            endIcon={<OpenInNewIcon />}
          >
            {t('registerToDownloadFeed')}
          </Button>
        )}
    </>
  );
}
