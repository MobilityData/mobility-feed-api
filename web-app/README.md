# Mobility Feeds API UI

This project is built with [Next.js](https://nextjs.org/) using the App Router.
Using node v24.12.0 (npm v11.6.2) (yarn v1.22.22)

## Installing packages
It is preferred to install the packages using `yarn` over `npm install`

## Configuration variables
Next.js can inject all necessary environment variables into the application in development mode and the JS bundle files. 
Steps to set environment variables:
- Create a file based on `.env.rename_me` with the name `.env.development` (for dev) or `.env` (for prod)
- Replace all key values with the desired content.
- Done! You can now start or build the application with the commands described below.

### Adding a new environment variable
To add a new environment variable, add the variable name to the `.env.{environment}` and modify the GitHub actions injecting the value per environment. When adding a new variable, make sure that the variable name is prefixed with `NEXT_PUBLIC_` for client-side usage; otherwise, the Next.js app will not read the variable on the client side.

## Available Scripts

In the project directory, you can run:

- Runs the app in the development mode:
It will automatically use environment variables located in `.env.development`
```
yarn run start:dev
```

- Running a production build
It will build then run the application in production and serve it locally using environment variables located in `.env`
Since it uses the files from the build, it will not hot reload
```
yarn run start:prod
```

Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

The page will reload if you make edits.\
You will also see any lint errors in the console.

- Launches the test runner in the interactive watch mode:
```
yarn test
```

- Builds the app for production:
```
yarn build:prod
```

It bundles the application in production mode using Next.js optimization.

The build is optimized and ready for deployment.

- Start the production build locally:
```
yarn start:prod
```

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
- E2E tests require a mock server to run to mock api endpoints
```
yarn run e2e:setup
```
Will start the dev environment with mock server. It's equal to running 
```
yarn run firebase:auth:emulator:dev + yarn run start:dev:mock"
```
In a different terminal,
```
yarn e2e:run
```
- Opens Cypress in the interactive GUI
```
yarn e2e:open
```

## API Types Generation

The project includes scripts for generating TypeScript types from OpenAPI specifications:

- Generate API types from main database catalog:
```
yarn generate:api-types
```

- Generate GBFS validator types:
```
yarn generate:gbfs-validator-types
```

## References

 - You can learn more in the [Next.js documentation](https://nextjs.org/docs).
 - To learn React, check out the [React documentation](https://reactjs.org/).
 - [Firebase Documentation](https://firebase.google.com/docs).
 - [next-intl Documentation](https://next-intl-docs.vercel.app/) for internationalization.
