import React from 'react';
import logo from './logo.svg';
import './App.css';
// import FirebaseUI from './FirebaseUI';

// import StyledFirebaseAuth from 'react-firebaseui/StyledFirebaseAuth'; // Import from react-firebaseui
import SignInScreen from './SignInScreen';
import AppRouter from './AppRouter';
import { RouterProvider } from 'react-router-dom';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <RouterProvider router={AppRouter} />
      </header>
    </div>
  );
}

// function App() {
//   return (
//     <div className="App">
//       <header className="App-header">
//         <img src={logo} className="App-logo" alt="logo" />
//         <p>
//           Edit <code>src/App.tsx</code> and save to reload.
//         </p>
//         <a
//           className="App-link"
//           href="https://reactjs.org"
//           target="_blank"
//           rel="noopener noreferrer"
//         >
//           Learn React
//         </a>
//       </header>
//     </div>
//   );
// }

export default App;
