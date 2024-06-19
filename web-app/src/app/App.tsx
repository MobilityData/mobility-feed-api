import './App.css';
import AppRouter from './router/Router';
import Footer from './components/Footer';
import Header from './components/Header';
import { BrowserRouter } from 'react-router-dom';
import AppSpinner from './components/AppSpinner';
import { RemoteConfigProvider } from './context/RemoteConfigProvider';
import { useDispatch } from 'react-redux';
import { anonymousLogin } from './store/profile-reducer';
import '../i18n';
import { Suspense } from 'react';

const Loader = () => <div>Loading...</div>;

function App(): React.ReactElement {
  require('typeface-muli'); // Load font
  const dispatch = useDispatch();
  dispatch(anonymousLogin()); // Login anonymously at the start of the app

  return (
    <RemoteConfigProvider>
      <div id='app-main-container'>
        <AppSpinner>
          <BrowserRouter>
            <Header />
            <Suspense fallback={<Loader />}>
              <AppRouter />
            </Suspense>
          </BrowserRouter>
        </AppSpinner>
        <Footer />
      </div>
    </RemoteConfigProvider>
  );
}

export default App;
