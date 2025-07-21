#
#   MobilityData 2024
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

import inspect
from functools import wraps
from pydantic import BaseModel, ValidationError
from fastapi import HTTPException


def validate_request(model: BaseModel, parameter_name: str, validate_none: bool = True):
    """
    Decorator to validate request parameters using Pydantic models.
    raises:
        HTTPException: 400, If the parameter is missing or invalid.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            func_args = inspect.getfullargspec(func).args
            print(func_args)
            index = func_args.index(parameter_name)
            value = args[index]
            if value:
                try:
                    model.model_validate(value)
                except ValidationError as e:
                    raise HTTPException(status_code=400, detail=str(e))
            else:
                if validate_none:
                    raise HTTPException(status_code=400, detail="Missing parameter")
            return await func(*args, **kwargs)

        return wrapper

    return decorator
