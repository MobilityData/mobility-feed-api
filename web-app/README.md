# Mobility Feeds API UI

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).
Using node v18.16.0 (npm v9.5.1)

## Available Scripts

In the project directory, you can run:

### `yarn start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

The page will reload if you make edits.\
You will also see any lint errors in the console.

### `yarn test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `yarn build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `yarn lint`

Executes linter on sources to review warnings and errors. It can be used to _auto_ fix issues when the solution is available by adding _--fix_ paramter. Full command: `yarn lint --fix`.

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
yarn start
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
