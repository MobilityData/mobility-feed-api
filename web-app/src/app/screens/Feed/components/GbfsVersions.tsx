import * as React from 'react';
import { ContentBox } from '../../../components/ContentBox';
import {
  Box,
  Button,
  Chip,
  IconButton,
  Link,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import {
  DownloadOutlined,
  ReportOutlined,
  LaunchOutlined,
  CheckCircle,
} from '@mui/icons-material';
import { type paths } from '../../../services/feeds/types';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import SummarizeIcon from '@mui/icons-material/Summarize';
import CodeIcon from '@mui/icons-material/Code';
import DateRangeIcon from '@mui/icons-material/DateRange';
import { WEB_VALIDATOR_LINK } from '../../../constants/Navigation';
import { formatServiceDateRange } from '../Feed.functions';
import { useTranslation } from 'react-i18next';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { type GBFSFeedType, type GBFSVersionType } from '../../../services/feeds/utils';
import { displayFormattedDate } from '../../../utils/date';

export interface GbfsVersionsProps {
  feed: GBFSFeedType;
}

export default function GbfsVersions({
  feed,
}: GbfsVersionsProps): React.ReactElement {
  const theme = useTheme();
  const { t } = useTranslation('gbfsFeatures');

  const sortVersions = (a: GBFSVersionType, b: GBFSVersionType) => {
    const na = (a.version ?? '0').replace(/[^0-9.]/g, '');
    const nb = (b.version ?? '0').replace(/[^0-9.]/g, '');
    return parseFloat(nb) - parseFloat(na);
  }

  return (
    <>
      <Typography
        sx={{ fontSize: { xs: 18, sm: 24 }, fontWeight: 'bold', mb: 1 }}
      >
        Versions
      </Typography>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'row',
          flexWrap: 'wrap',
          gap: 3,
          justifyContent: 'flex-end',
        }}
      >
        {feed?.versions?.sort((a, b) => sortVersions(a,b)).map((item, index) => (
          <ContentBox
            key={index}
            title={``}
            outlineColor={theme.palette.secondary.main}
            padding={2}
            sx={{
              my: 0,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
            width={{ xs: '100%' }}
          >
            <Box>
              <Box>
                <Typography
                  variant='h5'
                  sx={{
                    mb: 1,
                    fontWeight: 'bold',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  v{item.version}
                  <Chip
                    icon={
                      item.latest_validation_report?.total_error === 0 ? (
                        <CheckCircleIcon />
                      ) : (
                        <ErrorIcon />
                      )
                    }
                    label={
                      item.latest_validation_report?.total_error != null &&
                      item.latest_validation_report?.total_error > 0
                        ? `${item.latest_validation_report?.total_error} errors`
                        : 'no errors'
                    }
                    variant='outlined'
                    color={
                      item.latest_validation_report?.total_error != null &&
                      item.latest_validation_report?.total_error > 0
                        ? 'error'
                        : 'success'
                    }
                    sx={{ ml: 2 }}
                    clickable
                    component={Link}
                    href={item.latest_validation_report?.report_summary_url}
                    target='_blank'
                    rel='noreferrer'
                  />
                </Typography>
                <Typography
                  variant='caption'
                  component={'div'}
                  sx={{ mt: '-2px', mb: 2 }}
                >
                  Quality report updated at:{' '}
                  {displayFormattedDate(
                    item.latest_validation_report?.validated_at ?? '',
                  )}
                </Typography>
                <Typography variant='h6' sx={{ fontSize: '1.1rem' }}>
                  Auto-Discovery Url
                </Typography>
                <Box
                  sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}
                >
                  <Link sx={{wordWrap: 'break-word', wordBreak: 'break-all'}} href='https://data.lime.bike/api/partners/v2/gbfs/louisville/gbfs.json'>https://data.lime.bike/api/partners/v2/gbfs/louisville/gbfs.json</Link>  
                  {/* TODO: href={item.autoDiscovery}{item.autoDiscovery} */}
                  <ContentCopyIcon></ContentCopyIcon>
                </Box>
                <Box>
                  <Typography variant='h6' sx={{ mt: 1, fontSize: '1.1rem' }}>
                    Features
                  </Typography>
                  {item.endpoints?.map((endpoint, index) => (
                    <>
                    {endpoint.name != null && (
                      <Chip
                        component={Link}
                        key={index}
                        label={t(endpoint.name)}
                        color='info'
                        variant='filled'
                        sx={{ margin: '4px' }}
                        clickable
                        target='_blank'
                        rel='noreferrer'
                        href={`https://github.com/MobilityData/gbfs/blob/v${item.version}/gbfs.md#${endpoint.name}json`}
                        // TODO: ISSUE: some urls are like: https://github.com/MobilityData/gbfs/blob/v2.2/gbfs.md#vehicle_typesjson-added-in-v21
                        // the 'json-added-in-v21' makes the url unreliable
                        // it will still go to the page, but not the correct anchor
                      />
                    )}
                    </>
                    
                  ))}
                </Box>
              </Box>
            </Box>
            <Box
              sx={{
                width: '100%',
                display: 'flex',
                justifyContent: 'flex-end',
                gap: 2,
                mt: 3,
              }}
            >
              <Button
                variant='text'
                color='primary'
                href={''} // TODO: `https://gbfs-validator.mobilitydata.org/validator?url=${item.autoDiscovery}`
                target='_blank'
                rel='noreferrer'
                endIcon={<OpenInNewIcon></OpenInNewIcon>}
              >
                Run Validation Report
              </Button>
              <Button
                variant='contained'
                color='primary'
                href='' // TODO: item.autoDiscovery
                target='_blank'
                rel='noreferrer'
                endIcon={<OpenInNewIcon></OpenInNewIcon>}
              >
                Open Feed Url
              </Button>
            </Box>
          </ContentBox>
        ))}
      </Box>
    </>
  );
}
