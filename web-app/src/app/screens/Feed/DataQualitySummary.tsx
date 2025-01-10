import * as React from 'react';
import { Box, Chip, Tooltip } from '@mui/material';
import { CheckCircle, ReportOutlined } from '@mui/icons-material';
import { type components } from '../../services/feeds/types';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { WarningContentBox } from '../../components/WarningContentBox';
import VerifiedIcon from '@mui/icons-material/Verified';
import { useTranslation } from 'react-i18next';
import { verificationBadgeStyle } from '../../styles/VerificationBadge.styles';

export interface DataQualitySummaryProps {
  isOfficialFeed: boolean;
  latestDataset: components['schemas']['GtfsDataset'] | undefined;
}

export default function DataQualitySummary({
  isOfficialFeed,
  latestDataset,
}: DataQualitySummaryProps): React.ReactElement {
  const { t } = useTranslation('feeds');
  return (
    <Box data-testid='data-quality-summary' sx={{ my: 2 }}>
      {(latestDataset?.validation_report === undefined ||
        latestDataset.validation_report === null) && (
        <WarningContentBox>{t('errorLoadingQualityReport')}</WarningContentBox>
      )}
      {latestDataset?.validation_report !== undefined &&
        latestDataset.validation_report !== null && (
          <Box sx={{ display: 'flex', gap: 1 }}>
            {isOfficialFeed && (
              <Tooltip title={t('officialFeedTooltip')} placement='top'>
                <Chip
                  sx={verificationBadgeStyle}
                  icon={<VerifiedIcon sx={{ fill: 'white' }}></VerifiedIcon>}
                  label={t('officialFeed')}
                ></Chip>
              </Tooltip>
            )}
            <Chip
              data-testid='error-count'
              clickable
              component='a'
              href={latestDataset?.validation_report?.url_html}
              target='_blank'
              rel='noopener noreferrer'
              icon={
                latestDataset?.validation_report?.unique_error_count !==
                  undefined &&
                latestDataset?.validation_report?.unique_error_count > 0 ? (
                  <ReportOutlined />
                ) : (
                  <CheckCircle />
                )
              }
              label={
                latestDataset?.validation_report?.unique_error_count !==
                  undefined &&
                latestDataset?.validation_report?.unique_error_count > 0
                  ? `${latestDataset?.validation_report
                      ?.unique_error_count} ${t('common:feedback.errors')}`
                  : t('common:feedback.noErrors')
              }
              color={
                latestDataset?.validation_report?.unique_error_count !==
                  undefined &&
                latestDataset?.validation_report?.unique_error_count > 0
                  ? 'error'
                  : 'success'
              }
              variant='outlined'
            />

            <Chip
              data-testid='warning-count'
              clickable
              component='a'
              href={latestDataset?.validation_report?.url_html}
              target='_blank'
              rel='noopener noreferrer'
              icon={
                latestDataset?.validation_report?.unique_warning_count !==
                  undefined &&
                latestDataset?.validation_report?.unique_warning_count > 0 ? (
                  <ReportOutlined />
                ) : (
                  <CheckCircle />
                )
              }
              label={
                latestDataset?.validation_report?.unique_warning_count !==
                  undefined &&
                latestDataset?.validation_report?.unique_warning_count > 0
                  ? `${latestDataset?.validation_report
                      ?.unique_warning_count} ${t('common:feedback.warnings')}`
                  : t('common:feedback.no_warnings')
              }
              color={
                latestDataset?.validation_report?.unique_warning_count !==
                  undefined &&
                latestDataset?.validation_report?.unique_warning_count > 0
                  ? 'warning'
                  : 'success'
              }
              variant='outlined'
            />

            <Chip
              data-testid='info-count'
              icon={<InfoOutlinedIcon />}
              clickable
              component='a'
              href={latestDataset?.validation_report?.url_html}
              target='_blank'
              rel='noopener noreferrer'
              label={`${
                latestDataset?.validation_report?.unique_info_count ?? '0'
              } ${t('common:feedback.infoNotices')}`}
              color='primary'
              variant='outlined'
            />
          </Box>
        )}
    </Box>
  );
}
