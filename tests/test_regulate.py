import pytest

OWNER = "danny@example.com"


@pytest.mark.parametrize(
    ("permission", "expected"),
    [
        ({"type": "anyone", "role": "reader"}, "public"),
        ({"type": "anyone", "role": "writer"}, "public"),
        ({"type": "domain", "role": "reader", "domain": "example.com"}, "internal"),
        ({"type": "domain", "role": "reader", "domain": "other.com"}, "external"),
        (
            {"type": "user", "role": "writer", "emailAddress": "sam@example.com"},
            "internal",
        ),
        (
            {"type": "user", "role": "reader", "emailAddress": "sam@other.com"},
            "external",
        ),
        (
            {"type": "group", "role": "reader", "emailAddress": "team@other.com"},
            "external",
        ),
        ({"type": "user", "role": "owner", "emailAddress": OWNER}, "private"),
    ],
)
def test_each_permission_is_ranked_by_who_it_reaches(
    permission: dict[str, str], expected: str
) -> None:
    from gfunk.regulate import rank

    assert rank(permission, "example.com") == expected


def test_an_unknown_permission_type_is_treated_as_exposure_not_ignored() -> None:
    """A type we do not recognise is not a type we may quietly call safe."""
    from gfunk.regulate import rank

    assert (
        rank({"type": "carrierPigeon", "role": "reader"}, "example.com") == "external"
    )


def test_a_missing_domain_on_a_user_is_not_read_as_internal() -> None:
    from gfunk.regulate import rank

    assert rank({"type": "user", "role": "reader"}, "example.com") == "external"


@pytest.mark.parametrize(
    ("levels", "worst"),
    [
        (["private"], "private"),
        (["private", "internal"], "internal"),
        (["internal", "external"], "external"),
        (["external", "public", "internal"], "public"),
        ([], "private"),
    ],
)
def test_a_files_exposure_is_its_worst_permission(
    levels: list[str], worst: str
) -> None:
    from gfunk.regulate import worst_of

    assert worst_of(levels) == worst


def test_assess_reports_the_exposure_and_who_causes_it() -> None:
    from gfunk.regulate import assess

    file = {
        "id": "a",
        "name": "Q3 Numbers",
        "webViewLink": "https://x/a",
        "owners": [{"emailAddress": OWNER}],
        "permissions": [
            {"type": "user", "role": "owner", "emailAddress": OWNER},
            {"type": "user", "role": "writer", "emailAddress": "sam@other.com"},
            {"type": "anyone", "role": "reader", "allowFileDiscovery": False},
        ],
    }

    result = assess(file)

    assert result["exposure"] == "public"
    assert result["name"] == "Q3 Numbers"
    assert result["link"] == "https://x/a"
    assert "anyone with the link" in result["reached_by"]
    assert "sam@other.com" in result["reached_by"]
    assert OWNER not in result["reached_by"], "the owner is not an exposure"


def test_a_discoverable_public_file_says_so_because_it_is_worse() -> None:
    """Link-shared is an accident; search-indexed is an accident anyone can find."""
    from gfunk.regulate import assess

    file = {
        "id": "a",
        "name": "Notes",
        "owners": [{"emailAddress": OWNER}],
        "permissions": [
            {"type": "anyone", "role": "reader", "allowFileDiscovery": True}
        ],
    }

    assert "search" in " ".join(assess(file)["reached_by"]).lower()


def test_a_file_with_no_permissions_field_is_reported_as_unknown_not_private() -> None:
    """Drive omits permissions we may not read. Absence of evidence is not safety."""
    from gfunk.regulate import assess

    result = assess({"id": "a", "name": "Someone else's", "owners": []})

    assert result["exposure"] == "unknown"
    assert result["permission_ids"] == []


def test_assess_carries_the_ids_of_exposing_permissions_for_revoke() -> None:
    from gfunk.regulate import assess

    file = {
        "id": "a",
        "name": "Q3 Numbers",
        "owners": [{"emailAddress": OWNER}],
        "permissions": [
            {
                "id": "owner-perm",
                "type": "user",
                "role": "owner",
                "emailAddress": OWNER,
            },
            {
                "id": "sam-perm",
                "type": "user",
                "role": "writer",
                "emailAddress": "sam@other.com",
            },
        ],
    }

    result = assess(file)

    assert result["permission_ids"] == ["sam-perm"]


def test_audit_sorts_worst_first_then_by_name() -> None:
    from gfunk.regulate import audit

    def make(name: str, perms: list[dict[str, str]]) -> dict[str, object]:
        return {
            "id": name,
            "name": name,
            "owners": [{"emailAddress": OWNER}],
            "permissions": [
                {"type": "user", "role": "owner", "emailAddress": OWNER},
                *perms,
            ],
        }

    files = [
        make("zulu", []),
        make("alpha", [{"type": "user", "role": "reader", "emailAddress": "s@o.com"}]),
        make("bravo", [{"type": "anyone", "role": "reader"}]),
        make("alfa", [{"type": "user", "role": "reader", "emailAddress": "s@o.com"}]),
    ]

    assert [row["name"] for row in audit(files)] == ["bravo", "alfa", "alpha", "zulu"]


def test_audit_can_drop_the_files_that_are_not_shared_at_all() -> None:
    """The point is the exceptions; a clean file is noise in a risk report."""
    from gfunk.regulate import audit

    files = [
        {
            "id": "a",
            "name": "private",
            "owners": [{"emailAddress": OWNER}],
            "permissions": [{"type": "user", "role": "owner", "emailAddress": OWNER}],
        },
        {
            "id": "b",
            "name": "shared",
            "owners": [{"emailAddress": OWNER}],
            "permissions": [{"type": "anyone", "role": "reader"}],
        },
    ]

    assert [row["name"] for row in audit(files, shared_only=True)] == ["shared"]


def test_summarise_counts_each_exposure_level() -> None:
    from gfunk.regulate import summarise

    rows = [
        {"exposure": "public"},
        {"exposure": "public"},
        {"exposure": "external"},
        {"exposure": "private"},
    ]

    assert summarise(rows) == {"public": 2, "external": 1, "internal": 0}


@pytest.mark.parametrize("consumer", ["gmail.com", "googlemail.com"])
def test_a_consumer_account_has_no_colleagues_only_strangers(consumer: str) -> None:
    """No org sits behind gmail.com; a shared domain is coincidence, not trust."""
    from gfunk.regulate import rank

    other = {"type": "user", "role": "reader", "emailAddress": f"stranger@{consumer}"}

    assert rank(other, consumer) == "external"


def test_a_workspace_domain_still_treats_colleagues_as_internal() -> None:
    from gfunk.regulate import rank

    colleague = {"type": "user", "role": "reader", "emailAddress": "sam@acme.com"}

    assert rank(colleague, "acme.com") == "internal"
