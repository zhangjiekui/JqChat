from pydantic import BaseModel

from R2RV350.py.shared.abstractions import Token
from R2RV350.py.shared.api.models.base import R2RResults


class TokenResponse(BaseModel):
    access_token: Token
    refresh_token: Token


# Create wrapped versions of each response
WrappedTokenResponse = R2RResults[TokenResponse]
