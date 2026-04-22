from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from agent_port.config import settings
from agent_port.models.api_key import ApiKey  # noqa: F401
from agent_port.models.google_login_state import GoogleLoginState  # noqa: F401
from agent_port.models.instance_settings import InstanceSettings  # noqa: F401
from agent_port.models.integration import InstalledIntegration  # noqa: F401
from agent_port.models.log import LogEntry  # noqa: F401
from agent_port.models.oauth import OAuthState  # noqa: F401
from agent_port.models.oauth_auth_code import OAuthAuthCode  # noqa: F401
from agent_port.models.oauth_auth_request import OAuthAuthRequest  # noqa: F401
from agent_port.models.oauth_client import OAuthClient  # noqa: F401
from agent_port.models.oauth_revoked_token import OAuthRevokedToken  # noqa: F401
from agent_port.models.org import Org  # noqa: F401
from agent_port.models.org_membership import OrgMembership  # noqa: F401
from agent_port.models.tool_approval_request import ToolApprovalRequest  # noqa: F401
from agent_port.models.tool_cache import ToolCache  # noqa: F401
from agent_port.models.tool_execution import ToolExecutionSetting  # noqa: F401
from agent_port.models.user import User  # noqa: F401
from agent_port.models.waitlist import Waitlist  # noqa: F401
from alembic import context

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
