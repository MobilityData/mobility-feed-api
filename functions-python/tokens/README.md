# Tokens API Function
<!-- Refers github page open api schema -->

The tokens API function implements the tokens API described at [docs/DatabaseCatalogTokenAPI.yaml](https://mobilitydata.github.io/mobility-feed-api/SwaggerUI/index.html?urls.primaryName=Tokens).

# Local development

## Requirements

Python <= 3.10

## Installation & Usage

- Install dependencies
```bash
cd api
pip3 install -r requirements.txt
pip3 install -r requirements_dev.txt
```

## Environment variables
- Rename file `.env.rename_me` to `.env.local`
- Replace all values enclosed by `{{}}`
- Enjoy Coding!

## Linter
This repository uses Flak8 and Black for code styling

To run linter checks:

```bash
scripts/lint-tests.sh
```

You can also use the pre-commit installed through [requirements_dev.txt](api%2Frequirements_dev.txt) with
```bash
pre-commit install
pre-commit run --all-files
```

## Execute
```
./scripts/function-python-run.sh --function_name tokens
```