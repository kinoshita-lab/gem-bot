"""Google Calendar OAuth 2.0 authentication and API manager.

This module handles OAuth 2.0 authentication for Google Calendar API,
including token management, the authorization flow, and calendar operations.
"""

import asyncio
import json
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# OAuth 2.0 scopes for Google Calendar
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

# Default paths
DEFAULT_CREDENTIALS_FILE = "credentials.json"
DEFAULT_TOKENS_DIR = "history/tokens"


class CalendarAuthManager:
    """Manages OAuth 2.0 authentication for Google Calendar API."""

    def __init__(
        self,
        credentials_file: str = DEFAULT_CREDENTIALS_FILE,
        tokens_dir: str = DEFAULT_TOKENS_DIR,
    ):
        """Initialize the CalendarAuthManager.

        Args:
            credentials_file: Path to the OAuth 2.0 client credentials JSON file.
            tokens_dir: Directory to store user tokens.
        """
        self.credentials_file = credentials_file
        self.tokens_dir = Path(tokens_dir)
        self.tokens_dir.mkdir(parents=True, exist_ok=True)

        # Pending authorization flows: state -> {user_id, flow, future}
        self._pending_auth: dict[str, dict] = {}

        # Lock for thread-safe operations
        self._lock = threading.Lock()

    def _get_token_path(self, user_id: int) -> Path:
        """Get the token file path for a user.

        Args:
            user_id: Discord user ID.

        Returns:
            Path to the user's token file.
        """
        return self.tokens_dir / f"{user_id}.json"

    def is_credentials_configured(self) -> bool:
        """Check if OAuth credentials file exists and is valid.

        Returns:
            True if credentials.json exists and is valid.
        """
        status = self.get_configuration_status()
        return status["configured"]

    def get_configuration_status(self) -> dict:
        """Get detailed configuration status for credentials.json.

        Returns:
            Dict with configuration status:
            {
                "configured": bool,
                "error_code": str | None,
                    - "file_not_found": credentials.json doesn't exist
                    - "invalid_json": File is not valid JSON
                    - "missing_installed": Missing "installed" or "web" key
                    - "missing_client_id": Missing client_id
                    - "missing_client_secret": Missing client_secret
                "message": str,
                "setup_url": str,
            }
        """
        setup_url = "https://console.cloud.google.com/apis/credentials"

        # Check if file exists
        if not os.path.exists(self.credentials_file):
            return {
                "configured": False,
                "error_code": "file_not_found",
                "message": f"{self.credentials_file} not found",
                "setup_url": setup_url,
            }

        # Try to parse JSON
        try:
            with open(self.credentials_file, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return {
                "configured": False,
                "error_code": "invalid_json",
                "message": f"Invalid JSON format: {e}",
                "setup_url": setup_url,
            }
        except Exception as e:
            return {
                "configured": False,
                "error_code": "read_error",
                "message": f"Cannot read file: {e}",
                "setup_url": setup_url,
            }

        # Check for required structure (installed or web application)
        client_config = data.get("installed") or data.get("web")
        if not client_config:
            return {
                "configured": False,
                "error_code": "missing_installed",
                "message": "Missing 'installed' or 'web' key in credentials.json",
                "setup_url": setup_url,
            }

        # Check for required fields
        if not client_config.get("client_id"):
            return {
                "configured": False,
                "error_code": "missing_client_id",
                "message": "Missing 'client_id' in credentials.json",
                "setup_url": setup_url,
            }

        if not client_config.get("client_secret"):
            return {
                "configured": False,
                "error_code": "missing_client_secret",
                "message": "Missing 'client_secret' in credentials.json",
                "setup_url": setup_url,
            }

        # All checks passed
        return {
            "configured": True,
            "error_code": None,
            "message": "Configured",
            "setup_url": setup_url,
        }

    def is_user_authenticated(self, user_id: int) -> bool:
        """Check if a user has valid authentication tokens.

        Args:
            user_id: Discord user ID.

        Returns:
            True if the user has valid tokens.
        """
        token_path = self._get_token_path(user_id)
        if not token_path.exists():
            return False

        try:
            creds = self._load_credentials(user_id)
            return creds is not None and creds.valid
        except Exception:
            return False

    def _load_credentials(self, user_id: int) -> Credentials | None:
        """Load credentials for a user.

        Args:
            user_id: Discord user ID.

        Returns:
            Credentials object or None if not found/invalid.
        """
        token_path = self._get_token_path(user_id)
        if not token_path.exists():
            return None

        try:
            with open(token_path, "r") as f:
                token_data = json.load(f)

            creds = Credentials.from_authorized_user_info(token_data, SCOPES)

            # Refresh if expired
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self._save_credentials(user_id, creds)

            return creds
        except Exception:
            return None

    def _save_credentials(self, user_id: int, creds: Credentials) -> None:
        """Save credentials for a user.

        Args:
            user_id: Discord user ID.
            creds: Credentials object to save.
        """
        token_path = self._get_token_path(user_id)
        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes) if creds.scopes else SCOPES,
        }
        with open(token_path, "w") as f:
            json.dump(token_data, f)

    def get_credentials(self, user_id: int) -> Credentials | None:
        """Get valid credentials for a user.

        Args:
            user_id: Discord user ID.

        Returns:
            Valid Credentials object or None.
        """
        return self._load_credentials(user_id)

    def revoke_user(self, user_id: int) -> bool:
        """Revoke and delete user tokens.

        Args:
            user_id: Discord user ID.

        Returns:
            True if tokens were deleted, False if no tokens existed.
        """
        token_path = self._get_token_path(user_id)
        if token_path.exists():
            token_path.unlink()
            return True
        return False

    async def start_auth_flow(
        self,
        user_id: int,
        redirect_port: int = 8080,
    ) -> tuple[str, asyncio.Future]:
        """Start the OAuth 2.0 authorization flow.

        This method generates an authorization URL and sets up a local server
        to handle the callback.

        Args:
            user_id: Discord user ID.
            redirect_port: Port for the local redirect server.

        Returns:
            Tuple of (auth_url, future). The future will be resolved when
            authentication completes or fails.

        Raises:
            FileNotFoundError: If credentials.json is not found.
        """
        if not self.is_credentials_configured():
            raise FileNotFoundError(
                f"OAuth credentials file not found: {self.credentials_file}"
            )

        # Create OAuth flow
        redirect_uri = f"http://localhost:{redirect_port}/callback"
        flow = Flow.from_client_secrets_file(
            self.credentials_file,
            scopes=SCOPES,
            redirect_uri=redirect_uri,
        )

        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Generate authorization URL
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state=state,
            prompt="consent",
        )

        # Create a future to track completion
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        # Store pending auth info
        with self._lock:
            self._pending_auth[state] = {
                "user_id": user_id,
                "flow": flow,
                "future": future,
                "port": redirect_port,
            }

        # Start callback server in background
        asyncio.create_task(
            self._run_callback_server(state, redirect_port)
        )

        return auth_url, future

    async def _run_callback_server(self, state: str, port: int) -> None:
        """Run a temporary HTTP server to handle OAuth callback.

        Args:
            state: The state parameter for this auth flow.
            port: Port to listen on.
        """
        auth_manager = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                # Suppress logging
                pass

            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path != "/callback":
                    self.send_response(404)
                    self.end_headers()
                    return

                params = parse_qs(parsed.query)
                received_state = params.get("state", [None])[0]
                code = params.get("code", [None])[0]
                error = params.get("error", [None])[0]

                # Validate state
                with auth_manager._lock:
                    pending = auth_manager._pending_auth.get(received_state)

                if not pending:
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(
                        b"<html><body><h1>Invalid request</h1></body></html>"
                    )
                    return

                if error:
                    # Auth was denied or failed
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(
                        f"<html><body><h1>Authentication failed: {error}</h1>"
                        "<p>You can close this window.</p></body></html>".encode()
                    )
                    # Resolve future with error
                    loop = pending["future"].get_loop()
                    loop.call_soon_threadsafe(
                        pending["future"].set_exception,
                        Exception(f"OAuth error: {error}"),
                    )
                    return

                if code:
                    try:
                        # Exchange code for tokens
                        flow = pending["flow"]
                        flow.fetch_token(code=code)
                        creds = flow.credentials

                        # Save credentials
                        user_id = pending["user_id"]
                        auth_manager._save_credentials(user_id, creds)

                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(
                            "<html><body>"
                            "<h1>Authentication successful!</h1>"
                            "<p>You can close this window and return to Discord.</p>"
                            "</body></html>".encode()
                        )

                        # Resolve future with success
                        loop = pending["future"].get_loop()
                        loop.call_soon_threadsafe(
                            pending["future"].set_result,
                            True,
                        )
                    except Exception as e:
                        self.send_response(500)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(
                            f"<html><body><h1>Error: {e}</h1></body></html>".encode()
                        )
                        loop = pending["future"].get_loop()
                        loop.call_soon_threadsafe(
                            pending["future"].set_exception,
                            e,
                        )
                    finally:
                        # Clean up pending auth
                        with auth_manager._lock:
                            auth_manager._pending_auth.pop(received_state, None)

                # Signal to stop server
                self.server.should_stop = True

        # Run server in a thread
        def run_server():
            server = HTTPServer(("localhost", port), CallbackHandler)
            server.should_stop = False
            server.timeout = 1  # Check every second

            # Wait for callback with timeout (5 minutes)
            timeout_seconds = 300
            elapsed = 0
            while not server.should_stop and elapsed < timeout_seconds:
                server.handle_request()
                elapsed += 1

            if elapsed >= timeout_seconds:
                # Timeout - cancel the pending auth
                with auth_manager._lock:
                    pending = auth_manager._pending_auth.pop(state, None)
                if pending and not pending["future"].done():
                    loop = pending["future"].get_loop()
                    loop.call_soon_threadsafe(
                        pending["future"].set_exception,
                        TimeoutError("Authentication timed out"),
                    )

        # Run in thread to not block
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

    def get_auth_status(self, user_id: int) -> dict:
        """Get authentication status for a user.

        Args:
            user_id: Discord user ID.

        Returns:
            Dict with status information.
        """
        token_path = self._get_token_path(user_id)

        if not token_path.exists():
            return {
                "authenticated": False,
                "message": "Not connected",
            }

        try:
            creds = self._load_credentials(user_id)
            if creds and creds.valid:
                return {
                    "authenticated": True,
                    "message": "Connected",
                    "has_refresh_token": bool(creds.refresh_token),
                }
            else:
                return {
                    "authenticated": False,
                    "message": "Token expired or invalid",
                }
        except Exception as e:
            return {
                "authenticated": False,
                "message": f"Error: {e}",
            }

    def _get_calendar_service(self, user_id: int):
        """Get Google Calendar API service for a user.

        Args:
            user_id: Discord user ID.

        Returns:
            Google Calendar API service object.

        Raises:
            ValueError: If user is not authenticated.
        """
        creds = self.get_credentials(user_id)
        if not creds:
            raise ValueError("User is not authenticated")
        return build("calendar", "v3", credentials=creds)

    async def list_events(
        self,
        user_id: int,
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 10,
        calendar_id: str = "primary",
    ) -> list[dict]:
        """List events from user's calendar.

        Args:
            user_id: Discord user ID.
            time_min: Start time in ISO 8601 format (defaults to now).
            time_max: End time in ISO 8601 format (optional).
            max_results: Maximum number of events to return.
            calendar_id: Calendar ID (defaults to "primary").

        Returns:
            List of event dictionaries.
        """
        service = self._get_calendar_service(user_id)

        # Default time_min to now if not specified
        if not time_min:
            time_min = datetime.now(timezone.utc).isoformat()

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        events_result = await loop.run_in_executor(
            None,
            lambda: service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute(),
        )

        events = events_result.get("items", [])

        # Convert to simplified format
        result = []
        for event in events:
            start = event.get("start", {})
            end = event.get("end", {})
            result.append({
                "id": event.get("id"),
                "summary": event.get("summary", "(No title)"),
                "description": event.get("description", ""),
                "location": event.get("location", ""),
                "start": start.get("dateTime") or start.get("date"),
                "end": end.get("dateTime") or end.get("date"),
                "html_link": event.get("htmlLink"),
            })

        return result

    async def create_event(
        self,
        user_id: int,
        summary: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = "",
        calendar_id: str = "primary",
    ) -> dict:
        """Create a new event in user's calendar.

        Args:
            user_id: Discord user ID.
            summary: Event title.
            start_time: Start time in ISO 8601 format.
            end_time: End time in ISO 8601 format.
            description: Event description (optional).
            location: Event location (optional).
            calendar_id: Calendar ID (defaults to "primary").

        Returns:
            Created event dictionary.
        """
        service = self._get_calendar_service(user_id)

        # Determine if this is an all-day event or timed event
        # All-day events use 'date', timed events use 'dateTime'
        if "T" in start_time:
            start = {"dateTime": start_time, "timeZone": "Asia/Tokyo"}
            end = {"dateTime": end_time, "timeZone": "Asia/Tokyo"}
        else:
            start = {"date": start_time}
            end = {"date": end_time}

        event_body = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": start,
            "end": end,
        }

        loop = asyncio.get_event_loop()
        event = await loop.run_in_executor(
            None,
            lambda: service.events()
            .insert(calendarId=calendar_id, body=event_body)
            .execute(),
        )

        return {
            "id": event.get("id"),
            "summary": event.get("summary"),
            "start": event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
            "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"),
            "html_link": event.get("htmlLink"),
        }

    async def update_event(
        self,
        user_id: int,
        event_id: str,
        summary: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        description: str | None = None,
        location: str | None = None,
        calendar_id: str = "primary",
    ) -> dict:
        """Update an existing event.

        Args:
            user_id: Discord user ID.
            event_id: ID of the event to update.
            summary: New event title (optional).
            start_time: New start time in ISO 8601 format (optional).
            end_time: New end time in ISO 8601 format (optional).
            description: New description (optional).
            location: New location (optional).
            calendar_id: Calendar ID (defaults to "primary").

        Returns:
            Updated event dictionary.
        """
        service = self._get_calendar_service(user_id)

        # First, get the existing event
        loop = asyncio.get_event_loop()
        event = await loop.run_in_executor(
            None,
            lambda: service.events()
            .get(calendarId=calendar_id, eventId=event_id)
            .execute(),
        )

        # Update fields if provided
        if summary is not None:
            event["summary"] = summary
        if description is not None:
            event["description"] = description
        if location is not None:
            event["location"] = location
        if start_time is not None:
            if "T" in start_time:
                event["start"] = {"dateTime": start_time, "timeZone": "Asia/Tokyo"}
            else:
                event["start"] = {"date": start_time}
        if end_time is not None:
            if "T" in end_time:
                event["end"] = {"dateTime": end_time, "timeZone": "Asia/Tokyo"}
            else:
                event["end"] = {"date": end_time}

        # Update the event
        updated_event = await loop.run_in_executor(
            None,
            lambda: service.events()
            .update(calendarId=calendar_id, eventId=event_id, body=event)
            .execute(),
        )

        return {
            "id": updated_event.get("id"),
            "summary": updated_event.get("summary"),
            "start": updated_event.get("start", {}).get("dateTime") or updated_event.get("start", {}).get("date"),
            "end": updated_event.get("end", {}).get("dateTime") or updated_event.get("end", {}).get("date"),
            "html_link": updated_event.get("htmlLink"),
        }

    async def delete_event(
        self,
        user_id: int,
        event_id: str,
        calendar_id: str = "primary",
    ) -> bool:
        """Delete an event from user's calendar.

        Args:
            user_id: Discord user ID.
            event_id: ID of the event to delete.
            calendar_id: Calendar ID (defaults to "primary").

        Returns:
            True if deletion was successful.
        """
        service = self._get_calendar_service(user_id)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: service.events()
            .delete(calendarId=calendar_id, eventId=event_id)
            .execute(),
        )

        return True
