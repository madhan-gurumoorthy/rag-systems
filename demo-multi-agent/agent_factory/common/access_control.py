"""AD group-based access control for chatbot command handlers.

Resolves Slack/Teams user identities to corporate AD accounts via MS
Graph API, checks AD group membership, and provides a decorator for
gating handlers behind a named group.

The framework is pack-agnostic: group names, their AAD object ids, and
the implication hierarchy are all supplied at runtime by the
``[access_control]`` config block (typically ``secrets.toml``).  No
group names are hard-coded in this module.

Expected config shape (TOML)::

    [access_control]
    AZURE_TENANT_ID    = "..."
    AZURE_CLIENT_ID    = "..."
    AZURE_CLIENT_SECRET = "..."

    [[access_control.groups]]
    name    = "SG-MyApp-Admin"
    aad_id  = "00000000-0000-0000-0000-000000000001"
    implies = ["SG-MyApp-Operator", "SG-MyApp-Viewer"]

    [[access_control.groups]]
    name    = "SG-MyApp-Operator"
    aad_id  = "00000000-0000-0000-0000-000000000002"
    implies = ["SG-MyApp-Viewer"]

    [[access_control.groups]]
    name    = "SG-MyApp-Viewer"
    aad_id  = "00000000-0000-0000-0000-000000000003"
    implies = []

``implies`` lists the other group names a holder of ``name`` is also
treated as belonging to.  ``check_access(required="SG-MyApp-Viewer")``
will succeed for an Admin because Admin implies Viewer.
"""
from __future__ import annotations

import functools
import time
from typing import Callable, Optional

import httpx

from agent_factory.common.logging import get_logger
from agent_factory.infrastructure.settings import get_config

logger = get_logger("access_control")

_CACHE_TTL_SECONDS = 300  # 5 minutes
_membership_cache: dict[str, tuple[set[str], float]] = {}


class AccessControlError(Exception):
    """Raised when a user lacks the required AD group membership."""

    def __init__(self, user_id: str, required_group: str, channel: str = ""):
        self.user_id = user_id
        self.required_group = required_group
        self.channel = channel
        super().__init__(
            f"User {user_id} ({channel}) is not a member of {required_group}. "
            f"Access denied."
        )


def _coerce_groups(raw) -> list[dict]:
    """Normalise the config-supplied groups list to plain dicts.

    Accepts a list of dicts or a list of objects with ``name`` / ``aad_id``
    / ``implies`` attributes (Dynaconf's DynaBox).
    """
    out: list[dict] = []
    for entry in raw or []:
        if isinstance(entry, dict):
            name = entry.get("name", "")
            aad = entry.get("aad_id", "")
            imp = list(entry.get("implies", []) or [])
        else:
            name = getattr(entry, "name", "")
            aad = getattr(entry, "aad_id", "")
            imp = list(getattr(entry, "implies", []) or [])
        if name:
            out.append({"name": name, "aad_id": aad, "implies": imp})
    return out


class AccessController:
    """Manages AD group membership checks via MS Graph API.

    The group hierarchy and AAD ids are loaded from config at
    ``initialize()`` time; the framework itself ships no group names.
    """

    def __init__(self):
        self._tenant_id = ""
        self._client_id = ""
        self._client_secret = ""
        self._group_ids: dict[str, str] = {}
        self._group_hierarchy: dict[str, set[str]] = {}
        self._token: Optional[str] = None
        self._token_expires: float = 0
        self._enabled = False

    def initialize(self):
        """Load access control configuration from the app config."""
        config = get_config()
        ac_cfg = getattr(config, "access_control", None)
        if not ac_cfg:
            logger.warning(
                "Access control not configured ([access_control] missing). "
                "All commands will be allowed."
            )
            return

        self._tenant_id = getattr(ac_cfg, "AZURE_TENANT_ID", "")
        self._client_id = getattr(ac_cfg, "AZURE_CLIENT_ID", "")
        self._client_secret = getattr(ac_cfg, "AZURE_CLIENT_SECRET", "")

        groups = _coerce_groups(getattr(ac_cfg, "groups", None))
        self._group_ids = {g["name"]: g["aad_id"] for g in groups}
        self._group_hierarchy = {
            g["name"]: {g["name"]} | set(g["implies"]) for g in groups
        }

        if (
            self._tenant_id
            and self._client_id
            and self._client_secret
            and self._group_ids
        ):
            self._enabled = True
            logger.info(
                "Access control initialised with %d group(s): %s",
                len(self._group_ids),
                ", ".join(sorted(self._group_ids.keys())),
            )
        else:
            logger.warning(
                "Access control credentials or groups incomplete; "
                "running in permissive mode"
            )

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    async def _get_token(self) -> str:
        """Acquire or refresh an OAuth2 client-credentials token from Azure AD."""
        if self._token and time.time() < self._token_expires:
            return self._token

        url = f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            body = resp.json()

        self._token = body["access_token"]
        self._token_expires = time.time() + body.get("expires_in", 3600) - 60
        return self._token

    async def resolve_user_email(self, user_id: str, channel: str) -> str:
        """Resolve a Slack/Teams user identifier to an email address.

        Teams ids are typically a UPN or AAD object id; Slack ids are
        resolved via the Slack ``users.info`` API.
        """
        if channel == "teams":
            if "@" in user_id:
                return user_id
            token = await self._get_token()
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"https://graph.microsoft.com/v1.0/users/{user_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code == 200:
                    return resp.json().get("mail") or resp.json().get("userPrincipalName", user_id)
            return user_id

        if channel == "slack":
            try:
                config = get_config()
                slack_cfg = getattr(config, "slack", None)
                bot_token = getattr(slack_cfg, "SLACK_BOT_TOKEN", "") if slack_cfg else ""
                if bot_token:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.get(
                            "https://slack.com/api/users.info",
                            headers={"Authorization": f"Bearer {bot_token}"},
                            params={"user": user_id},
                        )
                        data = resp.json()
                        if data.get("ok"):
                            profile = data.get("user", {}).get("profile", {})
                            return profile.get("email", user_id)
            except Exception as e:
                logger.warning(f"Failed to resolve Slack user {user_id}: {e}")
            return user_id

        return user_id

    async def get_user_groups(self, user_email: str) -> set[str]:
        """Fetch the AD groups a user belongs to, with caching."""
        now = time.time()
        if user_email in _membership_cache:
            groups, cached_at = _membership_cache[user_email]
            if now - cached_at < _CACHE_TTL_SECONDS:
                return groups

        if not self._enabled:
            all_groups = set(self._group_ids.keys())
            _membership_cache[user_email] = (all_groups, now)
            return all_groups

        try:
            token = await self._get_token()
            user_groups: set[str] = set()

            for group_name, group_id in self._group_ids.items():
                if not group_id:
                    continue
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        f"https://graph.microsoft.com/v1.0/groups/{group_id}/members/$ref",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if resp.status_code == 200:
                        members = resp.json().get("value", [])
                        for member in members:
                            member_mail = member.get("mail") or member.get("userPrincipalName", "")
                            if member_mail.lower() == user_email.lower():
                                user_groups.add(group_name)
                                break

            if not user_groups:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        f"https://graph.microsoft.com/v1.0/users/{user_email}/memberOf",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if resp.status_code == 200:
                        memberships = resp.json().get("value", [])
                        member_group_ids = {m.get("id") for m in memberships}
                        for group_name, group_id in self._group_ids.items():
                            if group_id in member_group_ids:
                                user_groups.add(group_name)

            _membership_cache[user_email] = (user_groups, now)
            logger.debug(f"User {user_email} groups: {user_groups}")
            return user_groups

        except Exception as e:
            logger.error(f"Failed to check group membership for {user_email}: {e}")
            all_groups = set(self._group_ids.keys())
            _membership_cache[user_email] = (all_groups, now)
            return all_groups

    async def check_access(self, user_id: str, required_group: str, channel: str = "") -> bool:
        """Return True if ``user_id`` holds ``required_group`` (directly or via implication)."""
        if not self._enabled:
            return True

        user_email = await self.resolve_user_email(user_id, channel)
        user_groups = await self.get_user_groups(user_email)

        for group in user_groups:
            implied = self._group_hierarchy.get(group, {group})
            if required_group in implied:
                return True

        return False

    async def require_access(self, user_id: str, required_group: str, channel: str = "") -> None:
        """Check access and raise :class:`AccessControlError` if denied."""
        if not await self.check_access(user_id, required_group, channel):
            raise AccessControlError(user_id, required_group, channel)


access_controller = AccessController()


def require_group(group_name: str, channel: str = ""):
    """Decorator that gates a command handler behind an AD group check.

    The decorated function must accept ``user`` (or ``user_id``) as a
    keyword argument or as a positional argument resolvable to a string.
    The channel can be overridden per-call.

    Usage::

        @require_group("SG-MyApp-Operator", channel="slack")
        async def _handle_reingest(self, args, say, user):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            user_id = kwargs.get("user") or kwargs.get("user_id") or ""
            ch = channel

            if not user_id and len(args) > 1:
                for arg in args:
                    if isinstance(arg, str) and len(arg) > 2:
                        user_id = arg
                        break

            if not user_id:
                logger.warning(f"No user_id found for access check on {func.__name__}")

            if access_controller.is_enabled and user_id:
                try:
                    await access_controller.require_access(user_id, group_name, ch)
                except AccessControlError as e:
                    logger.warning(f"Access denied: {e}")
                    say_fn = kwargs.get("say")
                    if say_fn:
                        await say_fn(
                            text=f"Access denied. You need `{group_name}` membership to use this command. "
                                 f"Contact your manager to request access."
                        )
                        return
                    raise

            return await func(*args, **kwargs)
        return wrapper
    return decorator
