import './App.css';
import AppRouter from './router/Router';
import ContextProviders from './components/Context';
import Footer from './components/Footer';
import Header from './components/Header';
import { BrowserRouter } from 'react-router-dom';
import AppSpinner from './components/AppSpinner';

function App(): React.ReactElement {
  require('typeface-muli'); // Load font
  return (
    <ContextProviders>
      <div id='app-main-container'>
        <AppSpinner>
          <BrowserRouter>
            <Header />
            <AppRouter />
          </BrowserRouter>
        </AppSpinner>
        <Footer />
      </div>
    </ContextProviders>
  );
}

export default App;
