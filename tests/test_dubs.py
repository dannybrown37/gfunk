import pytest

from gfunk.dubs import (
    find_exact_duplicates,
    find_possible_duplicates,
    flatten_groups,
    group_label,
    group_rows,
    human_bytes,
    is_native,
    sort_by_waste,
    wasted_bytes,
)


PDF_A1 = {
    "id": "a1",
    "name": "report.pdf",
    "mimeType": "application/pdf",
    "md5Checksum": "aaa",
    "size": "100",
}
PDF_A2 = {
    "id": "a2",
    "name": "report (1).pdf",
    "mimeType": "application/pdf",
    "md5Checksum": "aaa",
    "size": "100",
}
PDF_B = {
    "id": "b1",
    "name": "other.pdf",
    "mimeType": "application/pdf",
    "md5Checksum": "bbb",
    "size": "50",
}
DOC_A1 = {
    "id": "d1",
    "name": "Notes",
    "mimeType": "application/vnd.google-apps.document",
}
DOC_A2 = {
    "id": "d2",
    "name": "Notes",
    "mimeType": "application/vnd.google-apps.document",
}
DOC_B = {
    "id": "d3",
    "name": "Other",
    "mimeType": "application/vnd.google-apps.document",
}
SHEET = {
    "id": "s1",
    "name": "Notes",
    "mimeType": "application/vnd.google-apps.spreadsheet",
}


@pytest.mark.parametrize(
    ("file", "expected"),
    [
        (PDF_A1, False),
        (DOC_A1, True),
        (SHEET, True),
        ({"mimeType": "application/vnd.google-apps.folder"}, True),
        ({}, False),
    ],
)
def test_is_native_checks_the_mime_prefix(
    file: dict[str, object], *, expected: bool
) -> None:
    assert is_native(file) == expected


def test_exact_duplicates_group_binaries_by_checksum() -> None:
    groups = find_exact_duplicates([PDF_A1, PDF_A2, PDF_B])
    assert groups == [[PDF_A1, PDF_A2]]


def test_exact_duplicates_ignore_native_files_even_if_checksum_present() -> None:
    fake = {**DOC_A1, "md5Checksum": "zzz"}
    fake2 = {**DOC_A2, "md5Checksum": "zzz"}
    assert find_exact_duplicates([fake, fake2]) == []


def test_exact_duplicates_skip_files_without_a_checksum() -> None:
    no_hash = {"id": "x", "name": "x", "mimeType": "application/pdf"}
    assert find_exact_duplicates([no_hash, no_hash]) == []


def test_singletons_are_not_a_duplicate_group() -> None:
    assert find_exact_duplicates([PDF_A1, PDF_B]) == []


def test_possible_duplicates_group_native_files_by_name_and_mime() -> None:
    groups = find_possible_duplicates([DOC_A1, DOC_A2, DOC_B, SHEET])
    assert groups == [[DOC_A1, DOC_A2]]


def test_possible_duplicates_ignore_binary_files() -> None:
    assert find_possible_duplicates([PDF_A1, PDF_A2]) == []


@pytest.mark.parametrize(
    ("group", "expected"),
    [
        ([PDF_A1, PDF_A2], 100),
        ([PDF_B], 0),
        ([], 0),
        (
            [
                {"size": "100"},
                {"size": "40"},
                {"size": "10"},
            ],
            50,
        ),
    ],
)
def test_wasted_bytes_is_everything_but_the_largest_copy(
    group: list[dict[str, object]], expected: int
) -> None:
    assert wasted_bytes(group) == expected


def test_sort_by_waste_puts_the_biggest_reclaim_first() -> None:
    small = [{"size": "10"}, {"size": "5"}]
    big = [{"size": "1000"}, {"size": "1000"}]
    assert sort_by_waste([small, big]) == [big, small]


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (0, "0B"),
        (512, "512B"),
        (1024, "1.0KB"),
        (1536, "1.5KB"),
        (1024 * 1024, "1.0MB"),
        (1024 * 1024 * 1024, "1.0GB"),
        (1024 * 1024 * 1024 * 1024, "1.0TB"),
    ],
)
def test_human_bytes_picks_the_right_unit(n: int, expected: str) -> None:
    assert human_bytes(n) == expected


def test_flatten_groups_tags_each_row_with_its_group_key() -> None:
    rows = flatten_groups([[PDF_A1, PDF_A2]], [[DOC_A1, DOC_A2]])
    assert [r["group_key"] for r in rows] == [
        ("exact", 0),
        ("exact", 0),
        ("possible", 0),
        ("possible", 0),
    ]


def test_group_rows_reconstructs_the_original_groups() -> None:
    rows = flatten_groups([[PDF_A1, PDF_A2], [PDF_B, PDF_B]], [])
    regrouped = group_rows(rows)
    assert [key for key, _ in regrouped] == [("exact", 0), ("exact", 1)]
    assert [len(members) for _, members in regrouped] == [2, 2]


def test_group_rows_reflects_deletions_when_a_row_is_removed() -> None:
    rows = flatten_groups([[PDF_A1, PDF_A2]], [])
    remaining = [r for r in rows if r["id"] != PDF_A2["id"]]
    assert group_rows(remaining) == [(("exact", 0), [rows[0]])]


def test_group_label_for_exact_shows_reclaimable_space_and_count() -> None:
    members = [
        {**PDF_A1, "group_key": ("exact", 0)},
        {**PDF_A2, "group_key": ("exact", 0)},
    ]
    assert group_label(("exact", 0), members) == (
        "Exact duplicates — 100B reclaimable (2 copies)"
    )


def test_group_label_for_possible_has_no_waste_figure() -> None:
    members = [{**DOC_A1, "group_key": ("possible", 0)}]
    assert group_label(("possible", 0), members) == (
        "Possible duplicates — check by hand (1 copies)"
    )
