import * as React from 'react';
import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import {
  Box,
  Button,
  Checkbox,
  Container,
  CssBaseline,
  FormControlLabel,
  FormGroup,
  Grid,
  InputAdornment,
  Pagination,
  TableContainer,
  TextField,
  Typography,
} from '@mui/material';
import { Search } from '@mui/icons-material';
import '../../styles/SignUp.css';
import '../../styles/FAQ.css';
import { selectUserProfile } from '../../store/profile-selectors';
import { useAppDispatch } from '../../hooks';
import { loadingFeeds } from '../../store/feeds-reducer';
import {
  selectFeedsData,
  selectFeedsStatus,
} from '../../store/feeds-selectors';
import { useSearchParams } from 'react-router-dom';
import SearchTable from './SearchTable';
import { Trans, useTranslation } from 'react-i18next';
import { theme } from '../../Theme';

const getDataTypeParamFromSelectedFeedTypes = (
  selectedFeedTypes: Record<string, boolean>,
): 'gtfs' | 'gtfs_rt' | undefined => {
  let dataTypeQueryParam: 'gtfs' | 'gtfs_rt' | undefined;
  if (selectedFeedTypes.gtfs && !selectedFeedTypes.gtfs_rt) {
    dataTypeQueryParam = 'gtfs';
  } else if (!selectedFeedTypes.gtfs && selectedFeedTypes.gtfs_rt) {
    dataTypeQueryParam = 'gtfs_rt';
  } else if (!selectedFeedTypes.gtfs && !selectedFeedTypes.gtfs_rt) {
    dataTypeQueryParam = undefined;
  }
  return dataTypeQueryParam;
};

const getInitialSelectedFeedTypes = (
  searchParams: URLSearchParams,
): Record<string, boolean> => {
  const gtfsSearch = searchParams.get('gtfs');
  const gtfsRtSearch = searchParams.get('gtfs_rt');

  if (gtfsSearch === null && gtfsRtSearch === null) {
    return {
      gtfs: true,
      gtfs_rt: true,
    };
  } else {
    return {
      gtfs: gtfsSearch === 'true',
      gtfs_rt: gtfsRtSearch === 'true',
    };
  }
};

export default function Feed(): React.ReactElement {
  const { t } = useTranslation('feeds');
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchLimit] = useState(20); // leaving possibility to edit in future
  const [selectedFeedTypes, setSelectedFeedTypes] = useState(
    getInitialSelectedFeedTypes(searchParams),
  );
  const [activeSearch, setActiveSearch] = useState(searchParams.get('q') ?? '');
  const [searchQuery, setSearchQuery] = useState(activeSearch);
  const [activePagination, setActivePagination] = useState(
    searchParams.get('o') !== null ? Number(searchParams.get('o')) : 1,
  );
  const user = useSelector(selectUserProfile);
  const dispatch = useAppDispatch();
  const feedsData = useSelector(selectFeedsData);
  const feedStatus = useSelector(selectFeedsStatus);

  const getPaginationOffset = (activePagination?: number): number => {
    const paginationParam =
      searchParams.get('o') !== null ? Number(searchParams.get('o')) : 1;
    const pagination = activePagination ?? paginationParam;
    const paginationOffset = (pagination - 1) * searchLimit;
    return paginationOffset;
  };

  useEffect(() => {
    if (user == null) return;

    const paginationOffset = getPaginationOffset(activePagination);
    dispatch(
      loadingFeeds({
        params: {
          query: {
            limit: searchLimit,
            offset: paginationOffset,
            search_query: activeSearch,
            data_type: getDataTypeParamFromSelectedFeedTypes(selectedFeedTypes),
            // Fixed status values for now, until a status filter is implemented
            // Filtering out deprecated feeds
            status: ['active', 'inactive', 'development'],
          },
        },
      }),
    );
  }, [user, activeSearch, activePagination, selectedFeedTypes, searchLimit]);

  useEffect(() => {
    const oldSearch = searchParams.get('q') ?? '';
    const oldPagination =
      searchParams.get('o') !== null ? Number(searchParams.get('o')) : 1;
    if (oldSearch === activeSearch && oldPagination === activePagination) {
      return;
    }

    const newSearchParams = new URLSearchParams();
    newSearchParams.set('q', activeSearch);
    if (activePagination !== 1) {
      newSearchParams.set('o', activePagination.toString());
    }
    setSearchParams(newSearchParams);
  }, [activeSearch, activePagination]);

  useEffect(() => {
    const newQuery = searchParams.get('q') ?? '';
    if (newQuery !== searchQuery) {
      setSearchQuery(newQuery);
      setActiveSearch(newQuery);
    }
    const newOffset =
      searchParams.get('o') !== null ? Number(searchParams.get('o')) : 1;
    if (newOffset !== activePagination) {
      setActivePagination(newOffset);
    }
  }, [searchParams]);

  const getSearchResultNumbers = (): string => {
    if (feedsData?.total !== undefined && feedsData?.total > 0) {
      const offset = getPaginationOffset(activePagination);
      const limit = offset + searchLimit;

      const startResult = 1 + offset;
      const endResult = limit > feedsData?.total ? feedsData.total : limit;
      const totalResults = feedsData?.total ?? '';
      return t('resultsFor', { startResult, endResult, totalResults });
    } else {
      return '';
    }
  };

  return (
    <Container component='main'>
      <CssBaseline />
      <Box
        sx={{
          mt: 12,
          display: 'flex',
          flexDirection: 'column',
        }}
        margin={{ xs: '80px 0px', m: '80px auto' }}
        maxWidth={{ xs: '100%', m: '1600px' }}
      >
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <Typography variant='h4' color='primary' sx={{ fontWeight: 700 }}>
              {t('feeds')}
            </Typography>
            <Typography variant='subtitle1'>{t('searchFor')}</Typography>
          </Grid>
          <Grid item xs={12} sx={{ display: 'flex', alignItems: 'center' }}>
            <Box
              component='form'
              onSubmit={(event) => {
                event.preventDefault();
                setActivePagination(1);
                setActiveSearch(searchQuery);
              }}
              sx={{
                display: 'flex',
                width: '100%',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <TextField
                sx={{
                  width: 'calc(100% - 85px)',
                }}
                value={searchQuery}
                placeholder={t('searchPlaceholder')}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                }}
                InputProps={{
                  startAdornment: (
                    <InputAdornment
                      style={{
                        cursor: 'pointer',
                      }}
                      onClick={() => {
                        setActivePagination(1);
                        setActiveSearch(searchQuery);
                      }}
                      position='start'
                    >
                      <Search />
                    </InputAdornment>
                  ),
                }}
              />
              <Button
                variant='contained'
                type='submit'
                sx={{ m: 1, height: '55px', mr: 0 }}
              >
                {t('common:search')}
              </Button>
            </Box>
          </Grid>

          <Grid item xs={12}>
            <Box
              width={'100%'}
              sx={{
                background: '#F8F5F5',
                borderRadius: '6px 0px 0px 6px',
                p: {
                  xs: 2,
                  md: 5,
                },
                color: 'black',
                fontSize: '18px',
                fontWeight: 700,
                mr: 0,
              }}
            >
              <Grid container spacing={1}>
                <Grid item xs={12} md={2}>
                  <div>
                    <div>{t('dataType')}</div>
                    <FormGroup
                      sx={{
                        flexDirection: {
                          xs: 'row',
                          md: 'column',
                        },
                      }}
                    >
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={selectedFeedTypes.gtfs}
                            onChange={(e) => {
                              setActivePagination(1);
                              setSelectedFeedTypes({
                                ...selectedFeedTypes,
                                gtfs: e.target.checked,
                              });
                            }}
                          />
                        }
                        label={t('common:gtfsSchedule')}
                      />
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={selectedFeedTypes.gtfs_rt}
                            onChange={(e) => {
                              setActivePagination(1);
                              setSelectedFeedTypes({
                                ...selectedFeedTypes,
                                gtfs_rt: e.target.checked,
                              });
                            }}
                          />
                        }
                        label={t('common:gtfsRealtime')}
                      />
                    </FormGroup>
                  </div>
                </Grid>

                {/* Content Area */}
                <Grid item xs={12} md={10}>
                  {feedStatus === 'loading' && (
                    <Grid item xs={12}>
                      <h3>{t('common:loading')}</h3>
                    </Grid>
                  )}

                  {feedStatus === 'error' && (
                    <Grid item xs={12}>
                      <h3>{t('common:errors.generic')}</h3>
                      <Typography>
                        <Trans i18nKey='errorAndContact'>
                          Please check your internet connection and try again.
                          If the problem persists{' '}
                          <a href='mailto:api@mobilitydata.org'>contact us</a>{' '}
                          for for further assistance.
                        </Trans>
                      </Typography>
                    </Grid>
                  )}

                  {feedsData !== undefined && feedStatus === 'loaded' && (
                    <>
                      {feedsData?.results?.length === 0 &&
                        activeSearch.trim().length > 0 && (
                          <Grid item xs={12}>
                            <h3>{t('noResults', { activeSearch })}</h3>
                            <Typography>{t('searchSuggestions')}</Typography>
                            <ul>
                              <li>
                                <Typography>
                                  {t('searchTips.twoDigit')}
                                </Typography>
                              </li>
                              <li>
                                <Typography>
                                  {t('searchTips.fullName')}
                                </Typography>
                              </li>
                              <li>
                                <Typography>
                                  {t('searchTips.checkSpelling')}
                                </Typography>
                              </li>
                            </ul>
                          </Grid>
                        )}
                      {feedsData?.results !== undefined &&
                        feedsData?.results !== null &&
                        feedsData?.results?.length > 0 && (
                          <TableContainer>
                            <Grid item xs={12}>
                              <Typography
                                variant='subtitle2'
                                sx={{ fontWeight: 'bold' }}
                                gutterBottom
                              >
                                {getSearchResultNumbers()}
                              </Typography>
                            </Grid>

                            <SearchTable feedsData={feedsData} />

                            <Pagination
                              sx={{
                                mt: 2,
                                button: {
                                  backgroundColor: 'white',
                                  color: theme.palette.primary.main,
                                },
                              }}
                              color='primary'
                              page={activePagination}
                              shape='rounded'
                              count={
                                feedsData.total !== undefined
                                  ? Math.ceil(feedsData.total / searchLimit)
                                  : 1
                              }
                              onChange={(event, value) => {
                                event.preventDefault();
                                setActivePagination(value);
                              }}
                            />
                          </TableContainer>
                        )}
                    </>
                  )}
                </Grid>
              </Grid>
            </Box>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
}
