import base64
import hashlib
import hmac
import json
import time
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import settings

bearer = HTTPBearer()
def sign(payload):
    return hmac.new(settings.auth_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
def issue(user):
    payload = base64.urlsafe_b64encode(json.dumps({"sub":user,"exp":time.time()+86400}).encode()).decode()
    return payload + "." + sign(payload)
def user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        payload, signature = credentials.credentials.split(".")
        if not hmac.compare_digest(signature, sign(payload)):
            raise ValueError()
        data = json.loads(base64.urlsafe_b64decode(payload))
        if data["exp"] < time.time() or data["sub"] not in {"alice","bob"}:
            raise ValueError()
        return data["sub"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401,"Invalid or expired session")
