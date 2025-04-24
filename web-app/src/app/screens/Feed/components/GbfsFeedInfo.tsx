import * as React from 'react';
import { ContentBox } from '../../../components/ContentBox';
import {
  Box,
  Button,
  Chip,
  Grid,
  type SxProps,
  Typography,
  Snackbar,
  styled,
  IconButton,
  Tooltip,
  useTheme,
  Link,
} from '@mui/material';
import { ContentCopy, ContentCopyOutlined } from '@mui/icons-material';
import {
  GBFSFeedType,
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../../services/feeds/utils';
import { type components } from '../../../services/feeds/types';
import { useTranslation } from 'react-i18next';

import { getDataFeatureUrl } from '../../../utils/consts';
import PublicIcon from '@mui/icons-material/Public';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import LinkIcon from '@mui/icons-material/Link';
import DatasetIcon from '@mui/icons-material/Dataset';
import LayersIcon from '@mui/icons-material/Layers';
import EmailIcon from '@mui/icons-material/Email';

import DateRangeIcon from '@mui/icons-material/DateRange';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import { FeedStatusIndicator } from '../../../components/FeedStatus';
import Locations from '../../../components/Locations';
import { formatServiceDateRange } from '../Feed.functions';
import SettingsIcon from '@mui/icons-material/Settings';
import BikeScooterIcon from '@mui/icons-material/BikeScooter';
import FeedAuthenticationSummaryInfo from './FeedAuthenticationSummaryInfo';
import { boxElementStyle, StyledTitleContainer } from '../Feed.styles';

export interface GbfsFeedInfoProps {
  feed: GBFSFeedType
}

export default function GbfsFeedInfo({
  feed,
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

      <Box sx={boxElementStyle}>
        <StyledTitleContainer>
          <LinkIcon></LinkIcon>
          <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
            Producer
          </Typography>
        </StyledTitleContainer>
        <Link href={feed?.provider_url} variant='body1'>
          {feed?.provider}
        </Link>
      </Box>

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
            Data Format
          </Typography>
        </StyledTitleContainer>
        <Typography variant='body1'>GBFS</Typography>
      </Box>

      <FeedAuthenticationSummaryInfo feed={feed} />
     
    </ContentBox>
  );
}
