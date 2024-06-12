import * as React from 'react';
import { useState } from 'react';
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

export default function Feed(): React.ReactElement {
  //   const { feedId } = useParams();
  const [searchText, setSearchText] = useState('');
  const user = useSelector(selectUserProfile);
  const dispatch = useAppDispatch();
  const feedsData = useSelector(selectFeedsData);

  const handleSearch = (): void => {
    if (user?.accessToken !== undefined) {
      dispatch(
        loadingFeeds({
          accessToken: user?.accessToken,
          params: {
            query: {
              search_query: searchText,
            },
          },
        }),
      );
    }
  };

  return (
    <Container component='main' sx={{ width: '100vw', m: 0 }}>
      <CssBaseline />
      <Box
        sx={{
          mt: 12,
          display: 'flex',
          flexDirection: 'column',
          m: 0,
          width: '90%',
        }}
        margin={{ xs: '0', sm: '80px' }}
      >
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <Typography sx={{ typography: { xs: 'h4', sm: 'h3' } }}>
              Feeds
            </Typography>
          </Grid>
          <Grid item xs={12}>
            <TextField
              sx={{
                width: '90vw',
              }}
              value={searchText}
              placeholder='Transit provider, feed name, or location'
              onChange={(e) => {
                setSearchText(e.target.value);
                // handleSearch();
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
              sx={{
                width: '90vw',
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
                        control={<Checkbox defaultChecked />}
                        label='GTFS Schedule'
                      />
                      <FormControlLabel
                        control={<Checkbox defaultChecked />}
                        label='GTFS Realtime'
                      />
                    </FormGroup>
                  </div>
                </Grid>
                <Grid xs={12} sm={9}>
                  {feedsData !== undefined && (
                    <div>1-10 of {feedsData.total} results</div>
                  )}
                  {feedsData?.results?.map(
                    (result: GTFSFeedType | GTFSRTFeedType, index) => {
                      return (
                        <SearchResultItem
                          key={'search-result-' + index}
                          result={result}
                        />
                      );
                    },
                  )}
                  <div>
                    <Button>Load {} more feeds </Button>
                  </div>
                </Grid>
              </Grid>
            </Box>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
}
