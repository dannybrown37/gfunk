"""Fictional demo data for TUI screenshots — 90s west coast hip-hop themed."""

from __future__ import annotations

from typing import Any

from gfunk.workspace import DOC_MIME, FOLDER_MIME, SHEET_MIME

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

DEMO_LABELS: list[dict[str, Any]] = [
    {
        "id": "INBOX",
        "name": "INBOX",
        "type": "system",
        "messages_total": 7,
        "messages_unread": 4,
    },
    {
        "id": "Label_studio",
        "name": "Studio Sessions",
        "type": "user",
        "messages_total": 12,
        "messages_unread": 3,
    },
    {
        "id": "Label_beats",
        "name": "Beat Tapes",
        "type": "user",
        "messages_total": 5,
        "messages_unread": 5,
    },
    {
        "id": "Label_vinyl",
        "name": "Vinyl Orders",
        "type": "user",
        "messages_total": 23,
        "messages_unread": 0,
    },
    {
        "id": "Label_shows",
        "name": "Live Shows",
        "type": "user",
        "messages_total": 8,
        "messages_unread": 2,
    },
    {
        "id": "CATEGORY_PROMOTIONS",
        "name": "CATEGORY_PROMOTIONS",
        "type": "system",
        "messages_total": 142,
        "messages_unread": 140,
    },
    {
        "id": "Label_empty",
        "name": "Old Demos",
        "type": "user",
        "messages_total": 0,
        "messages_unread": 0,
    },
]

# ---------------------------------------------------------------------------
# Messages — keyed by label id
# ---------------------------------------------------------------------------

_INBOX_MESSAGES: list[dict[str, Any]] = [
    {
        "id": "msg-001",
        "from": "Warren G <warren@regulators.net>",
        "subject": "Re: Saturday session at the studio",
        "snippet": "We can start laying down the bassline around 3pm...",
        "labels": ["INBOX"],
        "date": "1724500800000",
        "size": 4200,
    },
    {
        "id": "msg-002",
        "from": "Nate Dogg <nate@longbeach.fm>",
        "subject": "Hook ideas for the new track",
        "snippet": "Been working on a melody all week, smooth and easy...",
        "labels": ["INBOX"],
        "date": "1724414400000",
        "size": 3100,
    },
    {
        "id": "msg-003",
        "from": "DJ Quik <quik@compton.studio>",
        "subject": "Mixing desk specs for the remix",
        "snippet": "The SSL 4000 is booked Tuesday through Thursday...",
        "labels": ["INBOX"],
        "date": "1724328000000",
        "size": 8500,
    },
    {
        "id": "msg-004",
        "from": "Kurupt <kurupt@dpgc.com>",
        "subject": "Verse swap — your turn",
        "snippet": "Laid my 16 bars last night, attached the bounce...",
        "labels": ["INBOX"],
        "date": "1724241600000",
        "size": 1_200_000,
    },
    {
        "id": "msg-005",
        "from": "Suga Free <suga@pomona.fm>",
        "subject": "Talk box repair shop recommendation",
        "snippet": "There's a spot on Holt Ave that fixed mine in two days...",
        "labels": ["INBOX"],
        "date": "1724155200000",
        "size": 2400,
    },
    {
        "id": "msg-006",
        "from": "Battlecat <battlecat@westcoast.beats>",
        "subject": "MPC 3000 drum kit trade?",
        "snippet": "Got some clean 808 samples from the vault...",
        "labels": ["INBOX"],
        "date": "1724068800000",
        "size": 15000,
    },
    {
        "id": "msg-007",
        "from": "Daz Dillinger <daz@dpgc.com>",
        "subject": "Piano loop for the G-funk joint",
        "snippet": "Check the Wurlitzer patch, way smoother than Rhodes...",
        "labels": ["INBOX"],
        "date": "1723982400000",
        "size": 6300,
    },
]

_STUDIO_MESSAGES: list[dict[str, Any]] = [
    {
        "id": "msg-101",
        "from": "Sunset Sound <bookings@sunsetsound.com>",
        "subject": "Your reservation - Studio B, Aug 28-30",
        "snippet": "Confirmed three days in Studio B with the Neve console...",
        "labels": ["Label_studio"],
        "date": "1724500800000",
        "size": 3800,
    },
    {
        "id": "msg-102",
        "from": "Can-Am Studios <info@canam.la>",
        "subject": "Rate sheet update for fall bookings",
        "snippet": "Block rates available for sessions over five days...",
        "labels": ["Label_studio"],
        "date": "1724414400000",
        "size": 22000,
    },
    {
        "id": "msg-103",
        "from": "Warren G <warren@regulators.net>",
        "subject": "Engineer recommendation for the album",
        "snippet": "Call Chris, he mixed the whole Regulate tape...",
        "labels": ["Label_studio"],
        "date": "1724328000000",
        "size": 1800,
    },
]

_MESSAGES_BY_LABEL: dict[str, list[dict[str, Any]]] = {
    "INBOX": _INBOX_MESSAGES,
    "Label_studio": _STUDIO_MESSAGES,
    "Label_beats": [
        {
            "id": "msg-201",
            "from": "DJ Battlecat <battlecat@westcoast.beats>",
            "subject": "Summer bounce pack — 12 loops",
            "snippet": "All tempo-tagged, 90 to 100 bpm range...",
            "labels": ["Label_beats"],
            "date": "1724500800000",
            "size": 4_500_000,
        },
    ],
}

# ---------------------------------------------------------------------------
# Previews — keyed by message id
# ---------------------------------------------------------------------------

_PREVIEWS: dict[str, str] = {
    "msg-001": (
        "What's good,\n\n"
        "We can start laying down the bassline around 3pm. I already got the Minimoog "
        "patched in and the tempo locked at 92 bpm. Bring that wah pedal — the chorus "
        "section needs that funky sweep we talked about.\n\n"
        "Also, the engineer said the 2-inch tape machine is freshly calibrated. We "
        "should track the bass and keys to tape first, then dump to Pro Tools for the "
        "vocals.\n\n"
        "See you Saturday.\n\n"
        "— Warren"
    ),
    "msg-002": (
        "Hey,\n\n"
        "Been working on a melody all week. Something smooth and easy, laid back — "
        "the kind of hook you hum on the drive home. I recorded a rough take on my "
        "phone, sounds like it wants a Fender Rhodes underneath it.\n\n"
        "Let me know when you're free to run through it.\n\n"
        "— Nate"
    ),
    "msg-003": (
        "The SSL 4000 is booked Tuesday through Thursday but we can get the API "
        "console on Friday. Honestly for a remix I'd rather have the API anyway — "
        "the EQ is more musical.\n\n"
        "Bring your DAT tapes so we can transfer the stems. I'll have the Lexicon "
        "480L and the Eventide ready for vocal effects.\n\n"
        "— Quik"
    ),
    "msg-004": (
        "Laid my 16 bars last night. The bounce file is attached — 44.1k WAV, "
        "dry vocal, no effects. Your turn to lay something down over the second "
        "verse. The beat switches at bar 33, watch for it.\n\n"
        "The session file is on the shared drive under 'Collabs/August'.\n\n"
        "— Kurupt"
    ),
}

# ---------------------------------------------------------------------------
# Drive folders (for FolderBrowseScreen)
# ---------------------------------------------------------------------------

_DRIVE_FOLDERS: dict[str, list[dict[str, Any]]] = {
    "root": [
        {"id": "f-archive", "name": "gfunk-archive", "mimeType": FOLDER_MIME},
        {"id": "f-samples", "name": "Sample Library", "mimeType": FOLDER_MIME},
        {"id": "f-contracts", "name": "Contracts", "mimeType": FOLDER_MIME},
    ],
    "f-archive": [
        {"id": "f-2024", "name": "2024", "mimeType": FOLDER_MIME},
        {"id": "f-2023", "name": "2023", "mimeType": FOLDER_MIME},
    ],
    "f-samples": [
        {"id": "f-drums", "name": "Drum Kits", "mimeType": FOLDER_MIME},
        {"id": "f-keys", "name": "Keys and Synths", "mimeType": FOLDER_MIME},
        {"id": "f-bass", "name": "Basslines", "mimeType": FOLDER_MIME},
    ],
}


# ---------------------------------------------------------------------------
# DemoWorkspace — drop-in replacement for real Workspace in screenshot mode
# ---------------------------------------------------------------------------


class DemoWorkspace:
    """Fake workspace that returns demo data. No network calls."""

    def gmail_messages(
        self,
        label: str | None = None,
        term: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        _ = term
        if label is None:
            return []
        return list(_MESSAGES_BY_LABEL.get(label, []))[:limit]

    def gmail_preview(self, message_id: str) -> str:
        return _PREVIEWS.get(message_id, "(no preview available)")

    def children(
        self, folder_id: str = "root", limit: int = 200
    ) -> list[dict[str, Any]]:
        if folder_id == "root":
            return list(_DRIVE_FILES)[:limit]
        return list(_DRIVE_FOLDERS.get(folder_id, []))[:limit]

    def gmail_trash_message(self, message_id: str) -> dict[str, Any]:
        return {"id": message_id}

    def gmail_delete_label(self, label_id: str) -> None:
        _ = label_id

    def gmail_archive_message(
        self, message_id: str, *, parent: str = "root"
    ) -> dict[str, Any]:
        _ = parent
        return {"id": "archived", "name": f"{message_id}.pdf"}

    def gmail_archive_label(
        self, label_id: str, label_name: str, *, parent: str = "root"
    ) -> list[dict[str, Any]]:
        _ = label_id, label_name, parent
        return [{"id": "archived"}]

    def export(self, file_id: str, mime: str) -> bytes:
        _ = mime
        return _EXPORTS.get(file_id, b"(no content)")

    def sheet_tabs(self, file_id: str) -> list[str]:
        return _SHEET_TABS.get(file_id, ["Sheet1"])

    def sample(
        self, file_id: str, tab: str = "Sheet1", limit: int = 50
    ) -> list[dict[str, str]]:
        _ = tab
        return list(_SHEET_DATA.get(file_id, []))[:limit]

    def file_meta(self, file_id: str) -> dict[str, Any]:
        return _FILE_META.get(file_id, {"id": file_id, "name": file_id})

    def trash(self, file_id: str) -> dict[str, Any]:
        return {"id": file_id}

    def move(
        self, file_id: str, *, add_parent: str, remove_parent: str
    ) -> dict[str, Any]:
        _ = add_parent, remove_parent
        return {"id": file_id}

    def folder_names(self, ids: set[str]) -> dict[str, str]:
        return {fid: fid for fid in ids}

    def revoke(self, file_id: str, permission_id: str) -> None:
        _ = file_id, permission_id


# ---------------------------------------------------------------------------
# Grind (calendar) demo events
# ---------------------------------------------------------------------------

DEMO_GRIND_EVENTS: list[dict[str, Any]] = [
    {
        "summary": "Studio B session — tracking bass",
        "start": {"dateTime": "2024-08-26T10:00:00-07:00"},
        "end": {"dateTime": "2024-08-26T13:00:00-07:00"},
        "location": "Sunset Sound, Hollywood",
        "attendees": [
            {
                "email": "warren@regulators.net",
                "displayName": "Warren G",
                "responseStatus": "accepted",
            },
            {
                "email": "nate@longbeach.fm",
                "displayName": "Nate Dogg",
                "responseStatus": "tentative",
            },
        ],
    },
    {
        "summary": "Mix review with Quik",
        "start": {"dateTime": "2024-08-26T15:00:00-07:00"},
        "end": {"dateTime": "2024-08-26T16:30:00-07:00"},
        "location": "Can-Am Studios, Tarzana",
        "attendees": [
            {
                "email": "quik@compton.studio",
                "displayName": "DJ Quik",
                "responseStatus": "accepted",
            },
        ],
    },
    {
        "summary": "Vinyl pressing call",
        "start": {"dateTime": "2024-08-27T09:00:00-07:00"},
        "end": {"dateTime": "2024-08-27T09:30:00-07:00"},
        "description": (
            "Discuss the test pressing for the 12-inch single."
            " Need to confirm the lacquer cut."
        ),
    },
    {
        "summary": "Beat-making workshop",
        "start": {"dateTime": "2024-08-27T14:00:00-07:00"},
        "end": {"dateTime": "2024-08-27T17:00:00-07:00"},
        "location": "Digi+ Studios",
        "attendees": [
            {
                "email": "battlecat@westcoast.beats",
                "displayName": "Battlecat",
                "responseStatus": "accepted",
            },
            {
                "email": "daz@dpgc.com",
                "displayName": "Daz Dillinger",
                "responseStatus": "declined",
            },
        ],
    },
    {
        "summary": "Album listening party",
        "start": {"date": "2024-08-28"},
    },
    {
        "summary": "Master review",
        "start": {"dateTime": "2024-08-28T11:00:00-07:00"},
        "end": {"dateTime": "2024-08-28T12:00:00-07:00"},
    },
    {
        "summary": "Label meeting",
        "start": {"dateTime": "2024-08-29T10:00:00-07:00"},
        "end": {"dateTime": "2024-08-29T11:00:00-07:00"},
        "location": "Death Row offices",
    },
    {
        "summary": "Video shoot planning",
        "start": {"dateTime": "2024-08-29T14:00:00-07:00"},
        "end": {"dateTime": "2024-08-29T15:30:00-07:00"},
        "attendees": [
            {
                "email": "kurupt@dpgc.com",
                "displayName": "Kurupt",
                "responseStatus": "accepted",
            },
        ],
    },
    {
        "summary": "Radio promo call",
        "start": {"dateTime": "2024-08-29T16:00:00-07:00"},
        "end": {"dateTime": "2024-08-29T16:30:00-07:00"},
    },
]


# ---------------------------------------------------------------------------
# Snoop (Drive browser) demo files
# ---------------------------------------------------------------------------

_DRIVE_FILES: list[dict[str, Any]] = [
    {
        "id": "f-archive",
        "name": "gfunk-archive",
        "mimeType": FOLDER_MIME,
        "createdTime": "2023-01-15T10:00:00.000Z",
        "modifiedTime": "2024-08-20T14:00:00.000Z",
    },
    {
        "id": "f-samples",
        "name": "Sample Library",
        "mimeType": FOLDER_MIME,
        "createdTime": "2023-06-01T09:00:00.000Z",
        "modifiedTime": "2024-07-10T11:00:00.000Z",
    },
    {
        "id": "f-contracts",
        "name": "Contracts",
        "mimeType": FOLDER_MIME,
        "createdTime": "2024-01-20T08:00:00.000Z",
        "modifiedTime": "2024-08-15T16:00:00.000Z",
    },
    {
        "id": "doc-liner",
        "name": "Liner Notes — G-Funk Era Vol. 2",
        "mimeType": DOC_MIME,
        "createdTime": "2024-08-01T10:00:00.000Z",
        "modifiedTime": "2024-08-22T09:30:00.000Z",
    },
    {
        "id": "sheet-budget",
        "name": "Studio Budget Q3",
        "mimeType": SHEET_MIME,
        "createdTime": "2024-07-01T08:00:00.000Z",
        "modifiedTime": "2024-08-20T17:00:00.000Z",
    },
    {
        "id": "doc-rider",
        "name": "Tour Rider 2024",
        "mimeType": DOC_MIME,
        "createdTime": "2024-03-10T12:00:00.000Z",
        "modifiedTime": "2024-08-18T15:00:00.000Z",
    },
]

_EXPORTS: dict[str, bytes] = {
    "doc-liner": (
        b"G-Funk Era Vol. 2 -- Liner Notes\n\n"
        b"Produced at Sunset Sound and Can-Am Studios, summer 2024.\n"
        b"All tracks mixed on the SSL 4000 with the Lexicon 480L.\n\n"
        b"Executive Producer: Warren G\n"
        b"Mastered by: Bernie Grundman"
    ),
}

_SHEET_TABS: dict[str, list[str]] = {
    "sheet-budget": ["Budget", "Actuals"],
}

_SHEET_DATA: dict[str, list[dict[str, str]]] = {
    "sheet-budget": [
        {
            "Item": "Studio time",
            "Budget": "$12,000",
            "Spent": "$9,400",
            "Remaining": "$2,600",
        },
        {
            "Item": "Session musicians",
            "Budget": "$5,000",
            "Spent": "$3,200",
            "Remaining": "$1,800",
        },
        {"Item": "Mixing", "Budget": "$4,000", "Spent": "$4,000", "Remaining": "$0"},
        {"Item": "Mastering", "Budget": "$2,500", "Spent": "$0", "Remaining": "$2,500"},
        {
            "Item": "Vinyl pressing",
            "Budget": "$3,000",
            "Spent": "$1,500",
            "Remaining": "$1,500",
        },
        {"Item": "Artwork", "Budget": "$1,200", "Spent": "$800", "Remaining": "$400"},
    ],
}

_FILE_META: dict[str, dict[str, Any]] = {f["id"]: f for f in _DRIVE_FILES}


# ---------------------------------------------------------------------------
# Dubs (duplicates) demo rows
# ---------------------------------------------------------------------------

DEMO_DUBS_ROWS: list[dict[str, Any]] = [
    {
        "id": "dup-1a",
        "name": "808_kick_heavy.wav",
        "path": "Sample Library/Drum Kits/808_kick_heavy.wav",
        "size": 245_000,
        "group_key": ("exact", 0),
    },
    {
        "id": "dup-1b",
        "name": "808_kick_heavy.wav",
        "path": "gfunk-archive/2023/808_kick_heavy.wav",
        "size": 245_000,
        "group_key": ("exact", 0),
    },
    {
        "id": "dup-1c",
        "name": "808_kick_heavy.wav",
        "path": "Downloads/808_kick_heavy.wav",
        "size": 245_000,
        "group_key": ("exact", 0),
    },
    {
        "id": "dup-2a",
        "name": "Session Notes Aug 15",
        "path": "Contracts/Session Notes Aug 15",
        "size": 52_000,
        "group_key": ("possible", 0),
    },
    {
        "id": "dup-2b",
        "name": "Session Notes Aug 15 (copy)",
        "path": "gfunk-archive/Session Notes Aug 15 (copy)",
        "size": 53_000,
        "group_key": ("possible", 0),
    },
    {
        "id": "dup-3a",
        "name": "regulate_beat_v2.mp3",
        "path": "Sample Library/Basslines/regulate_beat_v2.mp3",
        "size": 4_800_000,
        "group_key": ("exact", 1),
    },
    {
        "id": "dup-3b",
        "name": "regulate_beat_v2.mp3",
        "path": "gfunk-archive/2024/regulate_beat_v2.mp3",
        "size": 4_800_000,
        "group_key": ("exact", 1),
    },
]


# ---------------------------------------------------------------------------
# Regulate (audit) demo rows
# ---------------------------------------------------------------------------

DEMO_REGULATE_ROWS: list[dict[str, Any]] = [
    {
        "id": "reg-1",
        "name": "Studio Budget Q3",
        "folder": "Contracts",
        "exposure": "external",
        "reached_by": ["warren@regulators.net", "quik@compton.studio"],
        "permission_ids": ["perm-1a", "perm-1b"],
    },
    {
        "id": "reg-2",
        "name": "Tour Rider 2024",
        "folder": "Contracts",
        "exposure": "public",
        "reached_by": ["anyone with the link"],
        "permission_ids": ["perm-2a"],
    },
    {
        "id": "reg-3",
        "name": "Liner Notes — G-Funk Era Vol. 2",
        "folder": "gfunk-archive",
        "exposure": "external",
        "reached_by": ["nate@longbeach.fm"],
        "permission_ids": ["perm-3a"],
    },
    {
        "id": "reg-4",
        "name": "Sample Library",
        "folder": "(root)",
        "exposure": "internal",
        "reached_by": ["battlecat@westcoast.beats", "daz@dpgc.com"],
        "permission_ids": ["perm-4a", "perm-4b"],
    },
    {
        "id": "reg-5",
        "name": "Session Notes Aug 15",
        "folder": "Contracts",
        "exposure": "external",
        "reached_by": ["kurupt@dpgc.com"],
        "permission_ids": ["perm-5a"],
    },
]


# ---------------------------------------------------------------------------
# Vibe (spreadsheet viewer) demo rows
# ---------------------------------------------------------------------------

DEMO_VIBE_ROWS: list[dict[str, str]] = [
    {
        "Track": "Regulate",
        "Producer": "Warren G",
        "BPM": "92",
        "Key": "G minor",
        "Status": "Mixed",
    },
    {
        "Track": "This DJ",
        "Producer": "Warren G",
        "BPM": "96",
        "Key": "C minor",
        "Status": "Tracking",
    },
    {
        "Track": "Indo Smoke",
        "Producer": "DJ Quik",
        "BPM": "88",
        "Key": "Eb major",
        "Status": "Mixed",
    },
    {
        "Track": "Ain't No Fun",
        "Producer": "Battlecat",
        "BPM": "90",
        "Key": "Ab major",
        "Status": "Mastered",
    },
    {
        "Track": "Summertime",
        "Producer": "Daz Dillinger",
        "BPM": "94",
        "Key": "F minor",
        "Status": "Tracking",
    },
    {
        "Track": "G-Funk Intro",
        "Producer": "Warren G",
        "BPM": "85",
        "Key": "Bb minor",
        "Status": "Draft",
    },
    {
        "Track": "Nate Dogg Hook",
        "Producer": "Nate Dogg",
        "BPM": "92",
        "Key": "G minor",
        "Status": "Recorded",
    },
    {
        "Track": "Keep It Gangsta",
        "Producer": "DJ Quik",
        "BPM": "98",
        "Key": "D minor",
        "Status": "Mixed",
    },
    {
        "Track": "Westside Ride",
        "Producer": "Battlecat",
        "BPM": "91",
        "Key": "A minor",
        "Status": "Draft",
    },
    {
        "Track": "Long Beach Nights",
        "Producer": "Daz Dillinger",
        "BPM": "87",
        "Key": "E minor",
        "Status": "Tracking",
    },
]
