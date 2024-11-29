import * as React from 'react';
import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import {
  Box,
  Button,
  Chip,
  Container,
  CssBaseline,
  Grid,
  InputAdornment,
  Pagination,
  Skeleton,
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
import { groupFeaturesByComponent } from '../../utils/consts';
import NestedCheckboxList, {
  type CheckboxStructure,
} from '../../components/NestedCheckboxList';
import {
  getDataTypeParamFromSelectedFeedTypes,
  getInitialSelectedFeedTypes,
} from './utility';
import { SearchHeader } from './styles';

export default function Feed(): React.ReactElement {
  const { t } = useTranslation('feeds');
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchLimit] = useState(20); // leaving possibility to edit in future
  const [selectedFeedTypes, setSelectedFeedTypes] = useState(
    getInitialSelectedFeedTypes(searchParams),
  );
  const [activeSearch, setActiveSearch] = useState(searchParams.get('q') ?? '');
  const [searchQuery, setSearchQuery] = useState(activeSearch);
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>(
    searchParams.get('features')?.split(',') ?? [],
  );
  const [featureCheckboxData, setFeatureCheckboxData] = useState<
    CheckboxStructure[]
  >([]);
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
    const newSearchParams = new URLSearchParams();
    if (activeSearch !== '') {
      newSearchParams.set('q', activeSearch);
    }

    if (activePagination !== 1) {
      newSearchParams.set('o', activePagination.toString());
    }
    if (selectedFeedTypes.gtfs) {
      newSearchParams.set('gtfs', 'true');
    } else {
      newSearchParams.delete('gtfs');
    }
    if (selectedFeedTypes.gtfs_rt) {
      newSearchParams.set('gtfs_rt', 'true');
    } else {
      newSearchParams.delete('gtfs_rt');
    }
    if (selectedFeatures.length > 0) {
      newSearchParams.set('features', selectedFeatures.join(','));
    }

    setSearchParams(newSearchParams);
  }, [activeSearch, activePagination, selectedFeedTypes, selectedFeatures]);

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

  function generateCheckboxStructure(): CheckboxStructure[] {
    const groupedFeatures = groupFeaturesByComponent();
    return Object.entries(groupedFeatures)
      .filter(([parent]) => parent !== 'Other')
      .sort(([keyA], [keyB]) => keyA.localeCompare(keyB))
      .map(([parent, features]) => ({
        title: parent,
        checked: features.every((feature) =>
          selectedFeatures.includes(feature.feature),
        ),
        seeChildren: true,
        type: 'checkbox',
        children: features.map((feature) => {
          return {
            title: feature.feature,
            type: 'checkbox',
            checked: selectedFeatures.some(
              (selectedFeature) => selectedFeature === feature.feature,
            ),
          };
        }),
      }));
  }

  function clearAllFilters(): void {
    setActivePagination(1);
    setSelectedFeedTypes({
      gtfs: false,
      gtfs_rt: false,
    });
    setSelectedFeatures([]);
  }

  React.useEffect(() => {
    setFeatureCheckboxData(generateCheckboxStructure());
  }, [selectedFeatures]);

  return (
    <Container component='main' maxWidth='xl'>
      <CssBaseline />
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
        }}
        mx={{ xs: 0, m: 'auto' }}
      >
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <Typography
              component='h1'
              variant='h4'
              color='primary'
              sx={{ fontWeight: 700 }}
            >
              {t('feeds')}
            </Typography>
            {activeSearch !== '' && (
              <Typography variant='subtitle1'>
                {t('searchFor')}: <b>{activeSearch}</b>
              </Typography>
            )}
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
                background: theme.palette.background.paper,
                borderRadius: '6px 0px 0px 6px',
                px: {
                  xs: 2,
                  md: 3,
                },
                py: 2,
                color: 'black',
                fontSize: '18px',
                fontWeight: 700,
                mr: 0,
              }}
            >
              <Grid
                container
                spacing={1}
                sx={{ flexWrap: { xs: 'wrap', md: 'nowrap' } }}
              >
                <Grid item xs={12} md={2} sx={{ minWidth: '275px', pr: 2 }}>
                  <SearchHeader variant='h6'>{t('dataType')}</SearchHeader>
                  <NestedCheckboxList
                    checkboxData={[
                      {
                        title: t('common:gtfsSchedule'),
                        checked: selectedFeedTypes.gtfs,
                        type: 'checkbox',
                      },
                      {
                        title: t('common:gtfsRealtime'),
                        checked: selectedFeedTypes.gtfs_rt,
                        type: 'checkbox',
                      },
                    ]}
                    onCheckboxChange={(checkboxData) => {
                      setActivePagination(1);
                      setSelectedFeedTypes({
                        ...selectedFeedTypes,
                        gtfs: checkboxData[0].checked,
                        gtfs_rt: checkboxData[1].checked,
                      });
                    }}
                  ></NestedCheckboxList>
                  <SearchHeader variant='h6'>Features</SearchHeader>
                  <NestedCheckboxList
                    checkboxData={featureCheckboxData}
                    onCheckboxChange={(checkboxData) => {
                      const selelectedFeatures: string[] = [];
                      checkboxData.forEach((checkbox) => {
                        if (checkbox.children !== undefined) {
                          checkbox.children.forEach((child) => {
                            if (child.checked) {
                              selelectedFeatures.push(child.title);
                            }
                          });
                        }
                      });
                      setActivePagination(1);
                      setSelectedFeatures(selelectedFeatures);
                    }}
                  />
                </Grid>

                <Grid item xs={12} md={10}>
                  <Box
                    sx={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: 1,
                      minHeight: '31px',
                      width: '100%',
                      alignItems: 'center',
                      mb: 1,
                    }}
                  >
                    {selectedFeedTypes.gtfs && (
                      <Chip
                        color='secondary'
                        size='small'
                        label={t('common:gtfsSchedule')}
                        onDelete={() => {
                          setActivePagination(1);
                          setSelectedFeedTypes({
                            ...selectedFeedTypes,
                            gtfs: false,
                          });
                        }}
                      />
                    )}
                    {selectedFeedTypes.gtfs_rt && (
                      <Chip
                        color='secondary'
                        size='small'
                        label={t('common:gtfsRealtime')}
                        onDelete={() => {
                          setActivePagination(1);
                          setSelectedFeedTypes({
                            ...selectedFeedTypes,
                            gtfs_rt: false,
                          });
                        }}
                      />
                    )}
                    {selectedFeatures.map((feature) => (
                      <Chip
                        color='secondary'
                        size='small'
                        label={feature}
                        key={feature}
                        onDelete={() => {
                          setSelectedFeatures(
                            selectedFeatures.filter((sf) => sf !== feature),
                          );
                        }}
                      />
                    ))}
                    {(selectedFeatures.length > 0 ||
                      selectedFeedTypes.gtfs_rt ||
                      selectedFeedTypes.gtfs) && (
                      <Button
                        variant={'text'}
                        onClick={clearAllFilters}
                        size={'small'}
                        color={'secondary'}
                      >
                        Clear All
                      </Button>
                    )}
                  </Box>
                  {feedStatus === 'loading' && (
                    <Grid item xs={12}>
                      <Skeleton
                        animation='wave'
                        variant='text'
                        sx={{ fontSize: '1rem', width: '200px' }}
                      />
                      <Skeleton
                        animation='wave'
                        variant='text'
                        sx={{ fontSize: '2rem', width: '100%' }}
                      />
                      <Skeleton
                        animation='wave'
                        variant='rectangular'
                        width={'100%'}
                        height={'1118px'}
                      />
                      <Skeleton
                        animation='wave'
                        variant='text'
                        sx={{ fontSize: '2rem', width: '320px' }}
                      />
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
