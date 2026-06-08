import os
from dynaconf import Dynaconf

_config = None

# ── App defaults (not secrets, safe to hardcode) ───────────────
# These are framework-level defaults that apply to every pack.
# Pack-specific values (RAG domain, agent name, etc.) live in the
# active pack.yaml — never in this module.
_DEFAULTS = {
    "LIGHTRAG_REQUESTS_CA_BUNDLE": os.path.join(
        os.path.dirname(__file__), "ca-bundle.crt"
    ),
    "LIGHTRAG_provider": "walmart_gateway",
    "LOG_FORMAT": "plain",
    # asyncpg pool tuning — override in secrets.toml per environment
    "POSTGRES_POOL_MIN_SIZE": 1,
    "POSTGRES_POOL_MAX_SIZE": 10,
    "POSTGRES_COMMAND_TIMEOUT_SECS": 30,
}


def get_config():
    """Lazy singleton that loads layered secrets and applies safe defaults.

    Secret sources are layered lowest-to-highest priority. Later files win
    on key conflict (Dynaconf merge order):

      1. /etc/secrets/secrets-common.toml — WCNP common bundle, mounted from
                                            the framework-level Akeyless path.
      2. /etc/secrets/secrets-pack.toml   — WCNP pack-specific bundle, mounted
                                            from the pack's own Akeyless path;
                                            overrides common where keys overlap.
      3. agent_factory/infrastructure/secrets.toml
                                         — dev-local override; only present
                                            outside the cluster.

    custom_prompts.toml, if present, is layered on top of all secret files.
    Hardcoded ``_DEFAULTS`` fill in any keys none of the above set.
    """
    global _config
    if _config is None:
        config_dir = os.path.dirname(__file__)
        local_secrets = os.path.join(config_dir, 'secrets.toml')
        custom_prompts = os.path.join(config_dir, 'custom_prompts.toml')

        candidate_paths = [
            '/etc/secrets/secrets-common.toml',
            '/etc/secrets/secrets-pack.toml',
            local_secrets,
        ]
        settings_files = [p for p in candidate_paths if os.path.exists(p)]

        if os.path.exists(custom_prompts):
            settings_files.append(custom_prompts)

        _config = Dynaconf(
            settings_files=settings_files,
            environments=True,
            load_dotenv=False,
        )

        for key, value in _DEFAULTS.items():
            if not hasattr(_config, key):
                _config.set(key, value)

    return _config