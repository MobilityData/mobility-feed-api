import './App.css';
import AppRouter from './router/Router';
import ContextProviders from './components/Context';
import Footer from './components/Footer';
import Header from './components/Header';
import { BrowserRouter } from 'react-router-dom';

function App(): React.ReactElement {
  require('typeface-muli'); // Load font
  return (
    <div className='container'>
      <ContextProviders>
        <BrowserRouter>
          <Header />
          <AppRouter />
          <Footer />
        </BrowserRouter>
      </ContextProviders>
    </div>
  );
}

export default App;
