"""
A tiny in-memory 'knowledge base' standing in for a real Bedrock Knowledge Base.
Domain: internal IT helpdesk (password resets, VPN, hardware, software requests).
Each doc is short on purpose -- this is for exercising the eval harness, not
for demonstrating retrieval quality at scale.
"""

DOCUMENTS = [
    {
        "id": "kb-001",
        "title": "Password reset policy",
        "text": (
            "Employees can reset their own password at any time via the "
            "self-service portal at password.corp.internal. Resets require "
            "MFA verification. Passwords must be at least 14 characters and "
            "are valid for 90 days before they expire."
        ),
    },
    {
        "id": "kb-002",
        "title": "VPN access and setup",
        "text": (
            "Corporate VPN uses Cisco AnyConnect. New employees are granted "
            "VPN access automatically on their first day. If the VPN client "
            "fails to connect, check that the local firewall allows outbound "
            "UDP 443, then restart the AnyConnect service."
        ),
    },
    {
        "id": "kb-003",
        "title": "Requesting new laptop hardware",
        "text": (
            "Hardware requests are submitted through the IT Service Catalog. "
            "Standard laptop refresh cycle is every 3 years. Expedited "
            "requests for broken hardware are fulfilled within 2 business days "
            "and require manager approval."
        ),
    },
    {
        "id": "kb-004",
        "title": "Installing approved software",
        "text": (
            "Employees can self-install any application listed in the "
            "Approved Software Catalog without a ticket. Anything outside "
            "the catalog requires a Security review, which typically takes "
            "5 business days."
        ),
    },
    {
        "id": "kb-005",
        "title": "Multi-factor authentication (MFA)",
        "text": (
            "MFA is required for all corporate logins. The company standard "
            "app is Okta Verify. Lost or new phones require re-enrollment "
            "through the IT helpdesk, since self-service re-enrollment is "
            "disabled for security reasons."
        ),
    },
    {
        "id": "kb-006",
        "title": "Shared drive and storage quotas",
        "text": (
            "Each employee gets 50GB on the shared drive by default. "
            "Requests for additional storage above 50GB require a business "
            "justification and manager sign-off, and are capped at 500GB."
        ),
    },
    {
        "id": "kb-007",
        "title": "Wi-Fi setup for office locations",
        "text": (
            "Office Wi-Fi network is 'CorpNet-Secure' and uses WPA2-Enterprise "
            "with your standard corporate credentials. Guest Wi-Fi is a "
            "separate network, 'CorpNet-Guest', and does not require "
            "credentials but is rate-limited."
        ),
    },
    {
        "id": "kb-008",
        "title": "Printer setup",
        "text": (
            "Printers are added automatically when connected to CorpNet-Secure "
            "using the PrintCorp client, which is pre-installed on all managed "
            "laptops. Manual driver installs are not supported."
        ),
    },
]
