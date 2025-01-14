from __future__ import annotations

import hashlib
import hmac
import logging
import random
import time

from dataclasses import dataclass
from typing import Any

import aiohttp
from aiohttp import ClientResponse

logging.basicConfig(
    level=logging.INFO,  # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Log format
)
_LOGGER = logging.getLogger(__name__)
BASE_URI = "https://api-e.ecoflow.com/"


class EcoflowException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)


def concat_params(params: dict[str, str]) -> str:
    if not params:
        return ""
    param_strings = [f"{key}={value}" for key, value in params.items()]
    return "&".join(param_strings)


class EcoFlowHttpClient:
    def __init__(self, apikey, secret):
        self._apikey = apikey
        self._secret = secret
        self.devices: dict[str, Any] = {}
        self._nonce = str(random.randint(10000, 1000000))
        self._timestamp = str(int(time.time() * 1000))

    async def get_data(self, endpoint: str, params: dict[str, str] = None):
        return await self.send_request(endpoint, "get", params)

    async def send_request(self, endpoint: str, method: str, params: dict[str, str] = None):
        async with aiohttp.ClientSession() as session:
            params = params or {}
            params_str = concat_params(params)
            headers = self.__headers(params_str)
            resp = await session.request(method,
                                         f"{BASE_URI}{endpoint}?{params_str}",
                                         headers=headers)

            self._nonce = str(random.randint(10000, 1000000))
            self._timestamp = str(int(time.time() * 1000))
            return await self.__get_response(resp)

    async def __get_response(self, resp: ClientResponse):
        if resp.status != 200:
            raise EcoflowException(f"Got HTTP status code {resp.status}: {resp.reason}")

        try:
            json_resp = await resp.json()
            response_message = json_resp.get("message", "No message field in response")
        except Exception as error:
            raise EcoflowException(f"Failed to parse response: {await resp.text()} Error: {error}")

        if response_message.lower() != "success":
            raise EcoflowException(f"API Response Message: {response_message}")

        return json_resp

    def __headers(self, params: str):
        sign = self.__sign(params)
        headers = {
            'accessKey': self._apikey,
            'nonce': self._nonce,
            'timestamp': self._timestamp,
            'sign': sign
        }
        return headers

    def __sign(self, query_params):
        target_str = f"accessKey={self._apikey}&nonce={self._nonce}&timestamp={self._timestamp}"
        if query_params:
            target_str = query_params + "&" + target_str
        return self.__encrypt(target_str)

    def __encrypt(self, message: str) -> str:
        message_bytes = message.encode('utf-8')
        secret_bytes = self._secret.encode('utf-8')
        hmac_obj = hmac.new(secret_bytes, message_bytes, hashlib.sha256)
        hmac_digest = hmac_obj.hexdigest()
        return hmac_digest
