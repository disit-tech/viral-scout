"""Google Ads on the Paid ads page: not read by viral-scout yet.

Claude reads Google Ads through Google's official connector (googleads/google-ads-mcp, read-only: account
discovery and GAQL reports), which needs its own Google Cloud OAuth login (docs/paid-ads.md). The official
connector can't create campaigns or change budgets, so Google changes stay in the Google Ads app for now.

Until the dashboard reads the Google Ads API itself, the page shows the account id with a link, and the cap check
refuses to start anything while a Google account is listed (its spend this month is unknown).
"""


def available():
    return False


def pull(account, goal="leads"):
    return {"ok": False, "account": account, "error": "not read by the dashboard yet: ask Claude (google-ads connector)",
            "manage_url": f"https://ads.google.com/aw/overview?ocid=&__c={account.replace('-', '')}", "campaigns": []}
