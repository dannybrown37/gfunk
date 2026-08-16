from types import SimpleNamespace
from unittest.mock import patch

import pytest
from googleapiclient.errors import HttpError

from gfunk.errors import explain

ENABLE_URL = (
    "https://console.developers.google.com/apis/api/drive.googleapis.com"
    "/overview?project=126417747528"
)


def http_error(status: int, message: str, reason: str = "") -> HttpError:
    body = (
        f'{{"error": {{"code": {status}, "message": "{message}", "errors": '
        f'[{{"message": "{message}", "reason": "{reason}"}}]}}}}'
    )
    resp = SimpleNamespace(status=status, reason="", get=lambda *_: None)
    return HttpError(resp, body.encode(), uri="u")


def test_a_disabled_api_names_the_console_page_to_click() -> None:
    exc = http_error(
        403,
        f"Google Drive API has not been used in project 126417747528 before or it "
        f"is disabled. Enable it by visiting {ENABLE_URL} then retry.",
        "accessNotConfigured",
    )
    with patch("sys.stdout.isatty", return_value=True):
        explained = explain(exc)

    assert "not enabled" in explained
    assert ENABLE_URL in explained
    assert explained.count(ENABLE_URL) == 2, (
        "the URL is both the link target and the visible, copyable text"
    )
    assert "Traceback" not in explained


def test_insufficient_scopes_says_to_drop_the_token_and_sign_in_again() -> None:
    exc = http_error(403, "Insufficient Permission", "insufficientPermissions")
    assert "gfunk get-down" in explain(exc)
    assert "token.json" in explain(exc)


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, "gfunk get-down"), (404, "does not exist"), (500, "Google refused")],
)
def test_other_failures_still_say_something_actionable(
    status: int, expected: str
) -> None:
    assert expected in explain(http_error(status, "boom"))
