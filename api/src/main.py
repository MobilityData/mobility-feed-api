#
#   MobilityData 2023
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
# This files allows to add extra application decorators aside from the generated code.
# The app created here is intended to replace the generated feeds_gen.main:app variable.
import os

import uvicorn
from fastapi import FastAPI

from feeds_gen.apis.datasets_api import router as DatasetsApiRouter
from feeds_gen.apis.feeds_api import router as FeedsApiRouter
from feeds_gen.apis.metadata_api import router as MetadataApiRouter
from feeds_gen.apis.search_api import router as SearchApiRouter
from feeds_gen.apis.licenses_api import router as LicensesApiRouter

# Using the starlettte implementaiton as fastapi implementation generates errors with CORS in certain situations and
# returns 200 in the method response. More info, https://github.com/tiangolo/fastapi/issues/1663#issuecomment-730362611
from starlette.middleware.cors import CORSMiddleware

from middleware.request_context_middleware import RequestContextMiddleware
from utils.logger import global_logging_setup


app = FastAPI(
    title="Mobility Data Catalog API",
    description="API as required in the _Proposed Version 1_ from the _Product Requirement Document for the Mobility "
    "Database_",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestContextMiddleware)

app.include_router(DatasetsApiRouter)
app.include_router(FeedsApiRouter)
app.include_router(MetadataApiRouter)
app.include_router(SearchApiRouter)
app.include_router(LicensesApiRouter)


@app.on_event("startup")
async def startup_event():
    global_logging_setup()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=os.getenv("PORT", 8080))
