"""Who can reach your Drive files, ranked worst first.

Pure functions over what Drive already returns: no I/O here, so the ranking —
the part that turns a permissions dump into an answer — is testable on its own.
"""

from collections import Counter
from typing import Any

# Worst last, so index doubles as severity.
LEVELS = ("unknown", "private", "internal", "external", "public")
OF_CONCERN = ("public", "external", "internal")

EXPOSURE_LABELS = {
    "public": "PUBLIC  ",
    "external": "EXTERNAL",
    "internal": "INTERNAL",
    "unknown": "UNKNOWN ",
    "private": "private ",
}

# No organisation sits behind these, so a shared domain is a coincidence rather
# than a colleague. Everyone outside the account itself is a stranger.
CONSUMER_DOMAINS = frozenset({"gmail.com", "googlemail.com"})


def domain_of(email: str) -> str:
    _, _, domain = email.partition("@")
    return domain.lower()


def rank(permission: dict[str, Any], owner_domain: str) -> str:
    """Rank one permission by how far it reaches beyond the owner."""
    kind = permission.get("type")

    if permission.get("role") == "owner":
        return "private"
    if kind == "anyone":
        return "public"
    if kind == "domain":
        target = str(permission.get("domain", "")).lower()
    elif kind in {"user", "group"}:
        target = domain_of(str(permission.get("emailAddress", "")))
    else:
        # An unrecognised type is not a type we may quietly call safe.
        return "external"

    shares_an_org = bool(target) and target == owner_domain
    if shares_an_org and owner_domain not in CONSUMER_DOMAINS:
        return "internal"
    return "external"


def worst_of(levels: list[str]) -> str:
    known = [level for level in levels if level in LEVELS]
    if not known:
        return "private"
    return max(known, key=LEVELS.index)


def reach_of(permission: dict[str, Any]) -> str:
    """Name the audience in the words a human would use to describe it."""
    if permission.get("type") == "anyone":
        if permission.get("allowFileDiscovery"):
            return "anyone, including Google search"
        return "anyone with the link"
    if permission.get("type") == "domain":
        return f"everyone at {permission.get('domain', 'an unnamed domain')}"
    return str(permission.get("emailAddress") or "an unnamed account")


def assess(file: dict[str, Any]) -> dict[str, Any]:
    """Rate one file's exposure and say who causes it."""
    owners = file.get("owners") or []
    owner = str(owners[0].get("emailAddress", "")) if owners else ""
    permissions = file.get("permissions")

    row = {
        "id": file.get("id"),
        "name": file.get("name"),
        "link": file.get("webViewLink"),
        "owner": owner,
    }

    # Drive omits `permissions` on files whose sharing we may not read. Absence of
    # evidence is not evidence of safety, so it gets its own level, not "private".
    if permissions is None:
        return {**row, "exposure": "unknown", "reached_by": []}

    ranked = [(rank(p, domain_of(owner)), p) for p in permissions]
    return {
        **row,
        "exposure": worst_of([level for level, _ in ranked]),
        "reached_by": [reach_of(p) for level, p in ranked if level != "private"],
    }


def audit(
    files: list[dict[str, Any]], *, shared_only: bool = False
) -> list[dict[str, Any]]:
    """Assess every file, worst exposure first, then alphabetically."""
    rows = [assess(file) for file in files]
    if shared_only:
        rows = [row for row in rows if row["exposure"] != "private"]
    rows.sort(key=lambda row: (-LEVELS.index(row["exposure"]), str(row["name"] or "")))
    return rows


def summarise(rows: list[dict[str, Any]]) -> dict[str, int]:
    counted = Counter(str(row["exposure"]) for row in rows)
    return {level: counted[level] for level in OF_CONCERN}
