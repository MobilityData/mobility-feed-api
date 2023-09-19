import './App.css';
import AppRouter from './router/Router';
import ContextProviders from './util-component/Context';
import Footer from './util-component/Footer';
import Header from './util-component/Header';
import { BrowserRouter } from 'react-router-dom';

function App(): React.ReactElement {
  require('typeface-muli'); // Load font
  return (
    <div className='container'>
      <BrowserRouter>
        <ContextProviders>
          <Header />
          <AppRouter />
          <Footer />
        </ContextProviders>
      </BrowserRouter>
    </div>
  );
}

export default App;
