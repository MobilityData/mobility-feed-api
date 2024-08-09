import './App.css';
import AppRouter from './router/Router';
import Footer from './components/Footer';
import Header from './components/Header';
import { BrowserRouter } from 'react-router-dom';
import AppSpinner from './components/AppSpinner';
import { RemoteConfigProvider } from './context/RemoteConfigProvider';
import { useDispatch } from 'react-redux';
import { anonymousLogin } from './store/profile-reducer';
import i18n from '../i18n';
import { Suspense, useEffect, useState } from 'react';
import { I18nextProvider } from 'react-i18next';
import { app } from '../firebase';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';

function App(): React.ReactElement {
  require('typeface-muli'); // Load font
  const dispatch = useDispatch();
  const [isAppReady, setIsAppReady] = useState(false);

  useEffect(() => {
    app.auth().onAuthStateChanged((user) => {
      if (user != null) {
        setIsAppReady(true);
      } else {
        setIsAppReady(false);
        dispatch(anonymousLogin());
      }
    });
    dispatch(anonymousLogin());
  }, [dispatch]);

  return (
    <RemoteConfigProvider>
      <I18nextProvider i18n={i18n}>
        <Suspense>
          <LocalizationProvider dateAdapter={AdapterDayjs}>
            <div id='app-main-container'>
              <AppSpinner>
                <BrowserRouter>
                  <Header />
                  {isAppReady ? <AppRouter /> : null}
                </BrowserRouter>
              </AppSpinner>
              <Footer />
            </div>
          </LocalizationProvider>
        </Suspense>
      </I18nextProvider>
    </RemoteConfigProvider>
  );
}

export default App;
