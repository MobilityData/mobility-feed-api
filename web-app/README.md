# Mobility Feeds API UI

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).
Using node v18.16.0 (npm v9.5.1)

## Installing packages
It is preferred to install the packages using `yarn` over `npm install`

## Configuration variables
React scripts can inject all necessary environment variables into the application in development mode and the JS bundle files. 
Steps to set environment variables:
- Create a file based on `src/.env.rename_me` with the name `src/.env.{environment}`. Example, `src/.env.dev`.
- Replace all key values with the desired content.
- Done! You can now start or build the application with the commands described below.

### Adding a new environment variable
To add a new environment variable, add the variable name to the `src/.env.{environment}` and modify the GitHub actions injecting the value per environment. When adding a new variable, make sure that the variable name is prefixed with `REACT_APP`; otherwise, the react app will not read the variable.

## Available Scripts

In the project directory, you can run:

- Runs the app in the development mode:
```
yarn start:dev
```

Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

The page will reload if you make edits.\
You will also see any lint errors in the console.

- Launches the test runner in the interactive watch mode:
```
yarn test
```

See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

- Builds the app locally to the `build` folder:
```
yarn build:dev
```

It bundles React in production mode for a target Firebase environment.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

- Linter check
```
yarn lint
```
Executes linter on sources to review warnings and errors

- Linter fix
```
yarn lint --fix
```

# Firebase integration

This application is powered by Firebase. 

_To access Firebase commands and features you need to create your own firebase project. Only MobilityData internal engineers have access to MobilityData's firebase projects_

## Firebase useful commands

- Switch project
```
npx firebase use {project_name_or_alias}
```
- Deploy to a _`preview`_ channel
```
npx firebase hosting:channel:deploy {channel_name}
```

# Component and E2E tests

Component and E2E tests are executed with [Cypress](https://docs.cypress.io/). Cypress tests are located in the cypress folder.

Cypress useful commands:
- Run local headless tests
```
yarn start:dev
```
In a different terminal,
```
yarn cypress-run
```
- Opens Cypress in the interactive GUI
```
yarn cypress-open
```
## References

 - You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).
 - To learn React, check out the [React documentation](https://reactjs.org/).
 - [Firebase Documentation](https://firebase.google.com/docs).
