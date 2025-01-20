"""Hub for Immich integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, TypedDict
from urllib.parse import urljoin
import time

import aiohttp

from homeassistant.exceptions import HomeAssistantError

_HEADER_API_KEY = "x-api-key"
_LOGGER = logging.getLogger(__name__)

_ALLOWED_MIME_TYPES = ["image/png", "image/jpeg"]

class AssetInfo(TypedDict):
    id: str
    type: str
    # Add other known fields as needed

class AlbumInfo(TypedDict):
    id: str
    name: str
    assets: list[AssetInfo]

class UserInfo(TypedDict):
    id: str
    email: str
    # Add other known fields as needed

@dataclass
class AssetStatistics:
    images: int
    videos: int
    total: int

class BaseAPIClient:
    """Base class for API operations."""
    
    def __init__(self, host: str, api_key: str) -> None:
        """Initialize."""
        _LOGGER.debug("Initializing BaseAPIClient with host: %s", host)
        self.host = host
        self.api_key = api_key
        self.headers = {
            "Accept": "application/json",
            _HEADER_API_KEY: self.api_key
        }
        _LOGGER.debug("BaseAPIClient initialized with headers: %s", self.headers)

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None
    ) -> Any:
        """Make an API request with common error handling."""
        start_time = time.time()
        url = urljoin(self.host, endpoint)
        _LOGGER.debug("Making %s request to %s", method, url)
        _LOGGER.debug("Request params: %s", params)
        _LOGGER.debug("Request json: %s", json_data)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=json_data
                ) as response:
                    response_time = time.time() - start_time
                    _LOGGER.debug("Response received in %.2f seconds", response_time)
                    
                    if response.status != 200:
                        raw_result = await response.text()
                        _LOGGER.error("API Error: %s - %s", response.status, raw_result)
                        _LOGGER.debug("Failed request details - URL: %s, Headers: %s", url, self.headers)
                        raise ApiError(f"API returned {response.status}: {raw_result}")
                    
                    result = await response.json()
                    _LOGGER.debug("API response: %s", result)
                    return result
        except aiohttp.ClientError as exception:
            _LOGGER.error("Connection error: %s", exception)
            _LOGGER.debug("Connection error details - URL: %s", url)
            raise CannotConnect from exception
        except Exception as e:
            _LOGGER.error("Unexpected error during API request: %s", str(e))
            _LOGGER.debug("Error details - URL: %s, Method: %s", url, method)
            raise

class ImmichHub(BaseAPIClient):
    """Immich API hub."""

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        _LOGGER.debug("Starting authentication")
        try:
            result = await self._make_request("POST", "/api/auth/validateToken")
            auth_status = result.get("authStatus", False)
            _LOGGER.debug("Authentication result: %s", auth_status)
            return auth_status
        except Exception as e:
            _LOGGER.error("Authentication failed: %s", str(e))
            raise

    async def get_my_user_info(self) -> UserInfo:
        """Get user info."""
        _LOGGER.debug("Getting user info")
        try:
            user_info = await self._make_request("GET", "/api/users/me")
            _LOGGER.debug("Retrieved user info: %s", user_info)
            return user_info
        except Exception as e:
            _LOGGER.error("Failed to get user info: %s", str(e))
            raise

    async def get_asset_info(self, asset_id: str) -> AssetInfo | None:
        """Get asset info."""
        _LOGGER.debug("Getting info for asset: %s", asset_id)
        try:
            asset_info = await self._make_request("GET", f"/api/assets/{asset_id}")
            _LOGGER.debug("Retrieved asset info: %s", asset_info)
            return asset_info
        except Exception as e:
            _LOGGER.error("Failed to get asset info: %s", str(e))
            return None

    async def download_asset(self, asset_id: str) -> bytes | None:
        """Download the asset."""
        _LOGGER.debug("Downloading asset: %s", asset_id)
        url = urljoin(self.host, f"/api/assets/{asset_id}/original")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={_HEADER_API_KEY: self.api_key}) as response:
                    if response.status != 200:
                        _LOGGER.error("Download error: %s", response.status)
                        return None
                    
                    if response.content_type not in _ALLOWED_MIME_TYPES:
                        _LOGGER.error("Unsupported MIME type: %s", response.content_type)
                        return None
                    
                    asset_data = await response.read()
                    _LOGGER.debug("Successfully downloaded asset: %s", asset_id)
                    return asset_data
        except aiohttp.ClientError as exception:
            _LOGGER.error("Download connection error: %s", exception)
            raise CannotConnect from exception

    async def list_favorite_images(self) -> list[AssetInfo]:
        """List all favorite images."""
        _LOGGER.debug("Listing favorite images")
        data = {"isFavorite": "true"}
        try:
            result = await self._make_request("POST", "/api/search/metadata", json_data=data)
            favorite_images = [asset for asset in result["assets"]["items"] if asset["type"] == "IMAGE"]
            _LOGGER.debug("Found %d favorite images", len(favorite_images))
            return favorite_images
        except Exception as e:
            _LOGGER.error("Failed to list favorite images: %s", str(e))
            raise

    async def list_all_albums(self) -> list[AlbumInfo]:
        """List all albums."""
        _LOGGER.debug("Listing all albums")
        try:
            albums = await self._make_request("GET", "/api/albums")
            _LOGGER.debug("Found %d albums", len(albums))
            return albums
        except Exception as e:
            _LOGGER.error("Failed to list albums: %s", str(e))
            raise

    async def list_album_images(self, album_id: str) -> list[AssetInfo]:
        """List all images in an album."""
        _LOGGER.debug("Listing images for album: %s", album_id)
        try:
            result = await self._make_request("GET", f"/api/albums/{album_id}")
            album_images = [asset for asset in result["assets"] if asset["type"] == "IMAGE"]
            _LOGGER.debug("Found %d images in album %s", len(album_images), album_id)
            return album_images
        except Exception as e:
            _LOGGER.error("Failed to list album images: %s", str(e))
            raise

    async def get_asset_statistics(self) -> AssetStatistics:
        """Get statistics for all assets."""
        _LOGGER.debug("Getting asset statistics")
        try:
            data = await self._make_request("GET", "/api/assets/statistics")
            stats = AssetStatistics(
                images=data.get("images", 0),
                videos=data.get("videos", 0),
                total=data.get("total", 0)
            )
            _LOGGER.debug("Retrieved asset statistics: %s", stats)
            return stats
        except Exception as e:
            _LOGGER.error("Failed to get asset statistics: %s", str(e))
            raise

    async def get_favorite_statistics(self) -> dict:
        """Get statistics for favorite assets."""
        _LOGGER.debug("Getting favorite assets statistics")
        try:
            params = {"isFavorite": "true"}
            result = await self._make_request("GET", "/api/assets/statistics", params=params)
            _LOGGER.debug("Favorite assets statistics: %s", result)
            return result
        except Exception as e:
            _LOGGER.error("Failed to search assets: %s", str(e))
            raise

    async def get_people(self) -> dict:
        """Get list of people with their details and statistics."""
        _LOGGER.debug("Getting list of people")
        try:
            response = await self._make_request("GET", "/api/people")
            people = response.get("people", [])
            total = response.get("total", 0)
            hidden = response.get("hidden", 0)
            _LOGGER.debug("Retrieved %d people (total: %d, hidden: %d)", len(people), total, hidden)
            return {
                "people": people,
                "total": total,
                "hidden": hidden
            }
        except Exception as e:
            _LOGGER.error("Failed to get people: %s", str(e))
            raise

    async def get_person_statistics(self, person_id: str) -> dict:
        """Get statistics for a specific person."""
        _LOGGER.debug("Getting statistics for person: %s", person_id)
        try:
            stats = await self._make_request("GET", f"/api/people/{person_id}/statistics")
            _LOGGER.debug("Statistics for person %s: %s", person_id, stats)
            return stats
        except Exception as e:
            _LOGGER.error("Failed to get statistics for person %s: %s", person_id, str(e))
            raise

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

class ApiError(HomeAssistantError):
    """Error to indicate that the API returned an error."""