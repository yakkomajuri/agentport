from pydantic import Field

from agent_port.integrations.types import (
    AuthMethod,
    OAuthAuth,
    RemoteMcpIntegration,
    TokenAuth,
)

_TOOL_CATEGORIES: dict[str, str] = {
    # Account
    "get_stripe_account_info": "Account",
    # Balance
    "retrieve_balance": "Balance",
    # Coupons
    "create_coupon": "Coupons",
    "list_coupons": "Coupons",
    # Customers
    "create_customer": "Customers",
    "list_customers": "Customers",
    # Disputes
    "list_disputes": "Disputes",
    "update_dispute": "Disputes",
    # Invoices
    "create_invoice": "Invoices",
    "create_invoice_item": "Invoices",
    "finalize_invoice": "Invoices",
    "list_invoices": "Invoices",
    # Payment links
    "create_payment_link": "Payment links",
    # Payment intents
    "list_payment_intents": "Payment intents",
    # Prices
    "create_price": "Prices",
    "list_prices": "Prices",
    # Products
    "create_product": "Products",
    "list_products": "Products",
    # Refunds
    "create_refund": "Refunds",
    # Subscriptions
    "cancel_subscription": "Subscriptions",
    "list_subscriptions": "Subscriptions",
    "update_subscription": "Subscriptions",
    # Search & documentation
    "search_stripe_resources": "Search & documentation",
    "fetch_stripe_resources": "Search & documentation",
    "search_stripe_documentation": "Search & documentation",
}


class StripeIntegration(RemoteMcpIntegration):
    id: str = "stripe"
    name: str = "Stripe"
    description: str = "Payments, subscriptions, and billing"
    docs_url: str = "https://docs.stripe.com/mcp"
    url: str = "https://mcp.stripe.com"
    auth: list[AuthMethod] = Field(
        default=[
            OAuthAuth(method="oauth"),
            TokenAuth(
                method="token",
                label="Stripe Secret Key",
                header="Authorization",
                format="Bearer {token}",
            ),
        ]
    )
    tool_categories: dict[str, str] = Field(default=_TOOL_CATEGORIES)
