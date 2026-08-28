from gfunk.demo_data import (
    DEMO_DUBS_ROWS,
    DEMO_GRIND_EVENTS,
    DEMO_LABELS,
    DEMO_REGULATE_ROWS,
    DEMO_VIBE_ROWS,
    DemoWorkspace,
)


class TestDemoData:
    def test_labels_not_empty(self) -> None:
        assert len(DEMO_LABELS) > 0
        assert all("id" in _ and "name" in _ for _ in DEMO_LABELS)

    def test_grind_events_have_required_fields(self) -> None:
        for ev in DEMO_GRIND_EVENTS:
            assert "summary" in ev
            assert "start" in ev

    def test_dubs_rows_have_group_keys(self) -> None:
        assert len(DEMO_DUBS_ROWS) > 0
        assert all("group_key" in r for r in DEMO_DUBS_ROWS)

    def test_regulate_rows_have_exposure(self) -> None:
        assert len(DEMO_REGULATE_ROWS) > 0
        assert all("exposure" in r for r in DEMO_REGULATE_ROWS)

    def test_vibe_rows_have_columns(self) -> None:
        assert len(DEMO_VIBE_ROWS) > 0
        assert all("Track" in r and "Producer" in r for r in DEMO_VIBE_ROWS)


class TestDemoWorkspace:
    def setup_method(self) -> None:
        self.ws = DemoWorkspace()

    def test_gmail_messages_inbox(self) -> None:
        msgs = self.ws.gmail_messages(label="INBOX")
        assert len(msgs) == 7
        assert all("id" in m for m in msgs)

    def test_gmail_messages_no_label(self) -> None:
        assert self.ws.gmail_messages(label=None) == []

    def test_gmail_messages_unknown_label(self) -> None:
        assert self.ws.gmail_messages(label="nonexistent") == []

    def test_gmail_messages_limit(self) -> None:
        msgs = self.ws.gmail_messages(label="INBOX", limit=2)
        assert len(msgs) == 2

    def test_gmail_preview_known(self) -> None:
        preview = self.ws.gmail_preview("msg-001")
        assert "bassline" in preview

    def test_gmail_preview_unknown(self) -> None:
        assert self.ws.gmail_preview("no-such-id") == "(no preview available)"

    def test_children_root(self) -> None:
        files = self.ws.children()
        assert len(files) > 0

    def test_children_subfolder(self) -> None:
        files = self.ws.children(folder_id="f-archive")
        assert len(files) == 2

    def test_children_unknown_folder(self) -> None:
        assert self.ws.children(folder_id="nope") == []

    def test_gmail_trash_message(self) -> None:
        result = self.ws.gmail_trash_message("msg-001")
        assert result["id"] == "msg-001"

    def test_gmail_delete_label(self) -> None:
        self.ws.gmail_delete_label("Label_studio")

    def test_gmail_archive_message(self) -> None:
        result = self.ws.gmail_archive_message("msg-001")
        assert "id" in result

    def test_gmail_archive_label(self) -> None:
        result = self.ws.gmail_archive_label("Label_studio", "Studio Sessions")
        assert len(result) == 1

    def test_export_known(self) -> None:
        data = self.ws.export("doc-liner", "text/plain")
        assert b"Liner Notes" in data

    def test_export_unknown(self) -> None:
        assert self.ws.export("nope", "text/plain") == b"(no content)"

    def test_sheet_tabs_known(self) -> None:
        tabs = self.ws.sheet_tabs("sheet-budget")
        assert "Budget" in tabs

    def test_sheet_tabs_unknown(self) -> None:
        assert self.ws.sheet_tabs("nope") == ["Sheet1"]

    def test_sample(self) -> None:
        rows = self.ws.sample("sheet-budget")
        assert len(rows) > 0
        assert "Item" in rows[0]

    def test_file_meta_known(self) -> None:
        meta = self.ws.file_meta("doc-liner")
        assert meta["name"] == "Liner Notes — G-Funk Era Vol. 2"

    def test_file_meta_unknown(self) -> None:
        meta = self.ws.file_meta("nope")
        assert meta["id"] == "nope"

    def test_trash(self) -> None:
        assert self.ws.trash("doc-liner")["id"] == "doc-liner"

    def test_move(self) -> None:
        result = self.ws.move("doc-liner", add_parent="f-archive", remove_parent="root")
        assert result["id"] == "doc-liner"

    def test_folder_names(self) -> None:
        result = self.ws.folder_names({"f-archive", "f-samples"})
        assert len(result) == 2

    def test_revoke(self) -> None:
        self.ws.revoke("doc-liner", "perm-1a")
