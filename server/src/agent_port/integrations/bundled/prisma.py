from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Backups
    "CreateBackupTool": "Backups",
    "ListBackupsTool": "Backups",
    "CreateRecoveryTool": "Backups",
    # Connection strings
    "CreateConnectionStringTool": "Connection strings",
    "DeleteConnectionStringTool": "Connection strings",
    "ListConnectionStringsTool": "Connection strings",
    # Databases
    "DeleteDatabaseTool": "Databases",
    "ListDatabasesTool": "Databases",
    # Queries
    "ExecuteSqlQueryTool": "Queries",
    "IntrospectSchemaTool": "Queries",
}


class PrismaIntegration(RemoteMcpIntegration):
    id: str = "prisma"
    name: str = "Prisma"
    description: str = "Database platform, ORM, and Prisma Postgres management"
    docs_url: str = "https://www.prisma.io/docs/postgres/integrations/mcp-server"
    url: str = "https://mcp.prisma.io/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
