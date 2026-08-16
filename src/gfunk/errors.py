"""Turn Google's API errors into the one sentence that says what to go do."""

import re

from googleapiclient.errors import HttpError

from gfunk.browser import hyperlink

URL_IN_MESSAGE = re.compile(r"https://\S+?(?=[.\s]*$|\s)")

UNAUTHORIZED = 401
NOT_FOUND = 404


def reason(exc: HttpError) -> str:
    details = getattr(exc, "error_details", None) or []
    for detail in details:
        if isinstance(detail, dict) and detail.get("reason"):
            return str(detail["reason"])
    return ""


def message(exc: HttpError) -> str:
    details = getattr(exc, "error_details", None) or []
    for detail in details:
        if isinstance(detail, dict) and detail.get("message"):
            return str(detail["message"])
    return str(exc)


def explain(exc: HttpError) -> str:
    """A cause and a next command, because a raw HttpError is neither."""
    text = message(exc)
    status = getattr(exc.resp, "status", None)
    why = reason(exc)

    if why == "accessNotConfigured":
        found = URL_IN_MESSAGE.search(text)
        # Link the URL itself: a bare label hides where it goes and can't be copied.
        where = hyperlink(found.group(), found.group()) if found else "the console"
        return (
            "That API is not enabled in your Google Cloud project.\n"
            f"  {where}\n"
            "Enabling takes a minute to propagate, then run the same command again."
        )
    if why in ("insufficientPermissions", "ACCESS_TOKEN_SCOPE_INSUFFICIENT"):
        return (
            "Your cached token lacks the scopes gfunk needs.\n"
            "  rm ~/.config/gfunk/token.json && gfunk get-down"
        )
    if status == UNAUTHORIZED:
        return "Your sign-in is no longer valid. Run:\n  gfunk get-down"
    if status == NOT_FOUND:
        return f"Google says that does not exist (404):\n  {text}"
    return f"Google refused the request ({status}):\n  {text}"
