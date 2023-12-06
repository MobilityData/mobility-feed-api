# Firebase Typescript Functions

## Overview
This project utilizes [Firebase Functions](https://firebase.google.com/docs/functions) within a monorepo architecture managed by [`yarn` workspaces](https://classic.yarnpkg.com/lang/en/docs/workspaces/). It employs Firebase for deploying serverless functions.

## Project Structure
- `functions` directory: Contains the Firebase Functions.
- `packages` directory: Contains the function-specific code.
- `firebase.json`: Configuration file for Firebase services.
- `package.json`: Defines workspaces and scripts for managing the monorepo.

## Development
### Adding New Functions
  1. **Create Function**: In the `packages/` directory, create a new directory for your function (e.g., `packages/my-new-function`).
  2. **Setup Function**: Inside your function directory, initialize it with `yarn init` and set up your function code.
  3. **Register Function**: Update `firebase.json` to include your new function. Add a new entry under `functions` with appropriate `source` and `codebase` values.
  4. **Dependencies**: Manage any specific dependencies for your function within its directory.
### Local Development
  1. **Build**: Run `yarn build` to build all workspaces.
  2. **Emulate Functions**: Use `firebase emulators:start` to test functions locally.

## Deployment
### Build All Functions
Run `yarn build` to build all the functions. 

### Deploy All Functions
To deploy the functions to Firebase use:
```shell
firebase deploy --only functions
```

### Deploy Functions Within a Codebase
To deploy a specific function to Firebase use:
```shell
firebase deploy --only functions:<codebase>
```

### Delete Functions
To delete a function from Firebase use:
```shell
firebase functions:delete <function_name>
```

## Testing
Run `yarn test` to execute tests across all workspaces.

## Linting
Run `yarn lint` to run linters across all workspaces.

---
