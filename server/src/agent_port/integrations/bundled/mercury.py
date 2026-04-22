from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Accounts
    "getAccount": "Accounts",
    "getAccounts": "Accounts",
    "getOrganization": "Accounts",
    # Cards
    "getAccountCards": "Cards",
    # Statements
    "getAccountStatements": "Statements",
    # Transactions
    "getTransaction": "Transactions",
    "listTransactions": "Transactions",
    # Categories
    "listCategories": "Categories",
    # Credit
    "listCredit": "Credit",
    # Recipients
    "getRecipient": "Recipients",
    "getRecipients": "Recipients",
    # Treasury
    "getTreasury": "Treasury",
    "getTreasuryTransactions": "Treasury",
}


class MercuryIntegration(RemoteMcpIntegration):
    id: str = "mercury"
    name: str = "Mercury"
    description: str = "Business banking, transactions, and treasury"
    docs_url: str = "https://docs.mercury.com/docs/what-is-mercury-mcp"
    url: str = "https://mcp.mercury.com/mcp"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
