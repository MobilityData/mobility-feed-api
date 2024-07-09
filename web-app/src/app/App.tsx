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
import { Suspense, useEffect } from 'react';
import { I18nextProvider } from 'react-i18next';

function App(): React.ReactElement {
  require('typeface-muli'); // Load font
  const dispatch = useDispatch();
  useEffect(() => {
    dispatch(anonymousLogin());
  }, [dispatch]);

  return (
    <RemoteConfigProvider>
      <I18nextProvider i18n={i18n}>
        <Suspense>
          <div id='app-main-container'>
            <AppSpinner>
              <BrowserRouter>
                <Header />
                <AppRouter />
              </BrowserRouter>
            </AppSpinner>
            <Footer />
          </div>
        </Suspense>
      </I18nextProvider>
    </RemoteConfigProvider>
  );
}

export default App;
