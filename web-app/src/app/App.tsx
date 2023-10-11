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
    <div className='container'>
      <ContextProviders>
        <AppSpinner>
          <BrowserRouter>
            <Header />
            <AppRouter />
            <Footer />
          </BrowserRouter>
        </AppSpinner>
      </ContextProviders>
    </div>
  );
}

export default App;
