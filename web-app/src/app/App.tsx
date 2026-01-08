import './App.css';
import AppRouter from './router/Router';
import { BrowserRouter } from 'react-router-dom';
import { RemoteConfigProvider } from './context/RemoteConfigProvider';
// import { useDispatch } from 'react-redux';
// import { anonymousLogin } from './store/profile-reducer';
import { Suspense, useState } from 'react';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import AppContainer from './AppContainer';
import { Helmet, HelmetProvider } from 'react-helmet-async';

function App(): React.ReactElement {
  const [isAppReady, setIsAppReady] = useState(true);

  // useEffect(() => {
  //   app.auth().onAuthStateChanged((user) => {
  //     if (user != null) {
  //       setIsAppReady(true);
  //     } else {
  //       setIsAppReady(false);
  //       dispatch(anonymousLogin());
  //     }
  //   });
  //   dispatch(anonymousLogin());
  // }, [dispatch]);

  return (
    <HelmetProvider>
      <Helmet>
        <meta
          name='description'
          content={
            "Access GTFS, GTFS Realtime, GBFS transit data with over 4,000 feeds from 70+ countries on the web's leading transit data platform."
          }
        />
      </Helmet>
        <Suspense>
          <LocalizationProvider dateAdapter={AdapterDayjs}>
            <BrowserRouter>
              <AppContainer>{isAppReady ? <AppRouter /> : null}</AppContainer>
            </BrowserRouter>
          </LocalizationProvider>
        </Suspense>
    </HelmetProvider>
  );
}

export default App;
