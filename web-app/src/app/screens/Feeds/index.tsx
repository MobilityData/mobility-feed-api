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
  TextField,
  Typography,
} from '@mui/material';
import { Search } from '@mui/icons-material';

import '../../styles/SignUp.css';
import '../../styles/FAQ.css';
import { selectUserProfile } from '../../store/profile-selectors';
import { useAppDispatch } from '../../hooks';
import { loadingFeeds } from '../../store/feeds-reducer';
import { selectFeedsData } from '../../store/feeds-selectors';
import {
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';
import SearchResultItem from './SearchResultItem';
import { useNavigate, useSearchParams } from 'react-router-dom';

const SEARCH_LIMIT_INCREASE = 20;

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

export default function Feed(): React.ReactElement {
  const navigate = useNavigate();

  const [searchParams, setSearchParams] = useSearchParams();
  const [searchLimit, setSearchLimit] = useState(10);
  const [selectedFeedTypes, setSelectedFeedTypes] = useState({
    gtfs: true,
    gtfs_rt: true,
  });

  const user = useSelector(selectUserProfile);
  const dispatch = useAppDispatch();
  const feedsData = useSelector(selectFeedsData);

  const handleSearch = (): void => {
    const searchQuery = searchParams.get('q') ?? undefined;
    if (
      user?.accessToken !== undefined &&
      searchQuery !== undefined &&
      searchQuery.trim() !== ''
    ) {
      setSearchLimit(10);
      dispatch(
        loadingFeeds({
          accessToken: user?.accessToken,
          params: {
            query: {
              limit: searchLimit,
              offset: 0,
              search_query: searchQuery,
            },
          },
        }),
      );
    }
  };

  useEffect(() => {
    const searchQuery = searchParams.get('q') ?? undefined;
    const timer = setTimeout(() => {
      if (
        user?.accessToken !== undefined &&
        searchQuery !== undefined &&
        searchQuery.trim() !== ''
      ) {
        dispatch(
          loadingFeeds({
            accessToken: user?.accessToken,
            params: {
              query: {
                limit: searchLimit,
                search_query: searchQuery,
                data_type:
                  getDataTypeParamFromSelectedFeedTypes(selectedFeedTypes),
              },
            },
          }),
        );
      }
    }, 400);

    return () => {
      clearTimeout(timer);
    };
  }, [searchLimit, searchParams, selectedFeedTypes]);

  return (
    <Container component='main' sx={{ width: '100vw', m: 0 }}>
      <CssBaseline />
      <Box
        sx={{
          mt: 12,
          display: 'flex',
          flexDirection: 'column',
          m: 0,
        }}
        width={{ xs: '100%', sm: '90%' }}
        margin={{ xs: '0', sm: '80px' }}
      >
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <Typography sx={{ typography: { xs: 'h3', sm: 'h3' } }}>
              Feeds
            </Typography>
          </Grid>
          <Grid item xs={12}>
            <TextField
              sx={{
                width: '90vw',
              }}
              value={searchParams.get('q') ?? ''}
              placeholder='Transit provider, feed name, or location'
              onChange={(e) => {
                const searchValue = e.target.value;
                setSearchParams({ q: searchValue });
              }}
              InputProps={{
                startAdornment: (
                  <InputAdornment
                    style={{
                      cursor: 'pointer',
                    }}
                    onClick={() => {
                      handleSearch();
                    }}
                    position='start'
                  >
                    <Search />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={12}>
            <Box
              width={{ xs: '100vw', sm: '90vw' }}
              sx={{
                background: '#F8F5F5',
                borderRadius: '6px 0px 0px 6px',
                p: 5,
                color: 'black',
                fontSize: '18px',
                fontWeight: 700,
                mr: 0,
              }}
            >
              <Grid container spacing={2}>
                <Grid xs={12} sm={3}>
                  <div>
                    <div>Data Type</div>
                    <FormGroup>
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={selectedFeedTypes.gtfs}
                            onChange={(e) => {
                              setSelectedFeedTypes({
                                ...selectedFeedTypes,
                                gtfs: e.target.checked,
                              });
                            }}
                          />
                        }
                        label='GTFS Schedule'
                      />
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={selectedFeedTypes.gtfs_rt}
                            onChange={(e) => {
                              setSelectedFeedTypes({
                                ...selectedFeedTypes,
                                gtfs_rt: e.target.checked,
                              });
                            }}
                          />
                        }
                        label='GTFS Realtime'
                      />
                    </FormGroup>
                  </div>
                </Grid>
                {feedsData?.total !== undefined && (
                  <Grid container spacing={2} xs={12} sm={9}>
                    <Grid item xs={12}>
                      {feedsData.total > 0 && '1-'}
                      {feedsData.total !== undefined &&
                      feedsData.total < searchLimit
                        ? feedsData.total
                        : searchLimit}{' '}
                      of {feedsData.total} results
                    </Grid>
                    <Grid container spacing={2} xs={12}>
                      {feedsData?.results?.map(
                        (result: GTFSFeedType | GTFSRTFeedType, index) => {
                          if (result === undefined) return <></>;
                          return (
                            <Grid
                              item
                              key={'search-result-' + index}
                              width={{ xs: '100%', sm: '80%' }}
                              onClick={() => {
                                navigate(`/feeds/${result.id}`);
                              }}
                              sx={{
                                cursor: 'pointer',
                              }}
                            >
                              <SearchResultItem result={result} />
                            </Grid>
                          );
                        },
                      )}
                    </Grid>
                    <Grid item xs={12}>
                      <Button
                        variant='contained'
                        disabled={
                          feedsData?.total !== undefined &&
                          searchLimit >= feedsData?.total
                        }
                        onClick={() => {
                          setSearchLimit(searchLimit + SEARCH_LIMIT_INCREASE);
                        }}
                      >
                        Load {SEARCH_LIMIT_INCREASE} more feeds
                      </Button>
                    </Grid>
                  </Grid>
                )}
              </Grid>
            </Box>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
}
