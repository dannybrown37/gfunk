from pathlib import Path

from gfunk.workspace import read_script_files, write_script_files


def test_write_script_files_uses_type_extensions(tmp_path: Path) -> None:
    files = [
        {"name": "Code", "type": "SERVER_JS", "source": "function main() {}"},
        {"name": "index", "type": "HTML", "source": "<p>hi</p>"},
        {"name": "appsscript", "type": "JSON", "source": "{}"},
    ]

    written = write_script_files(files, tmp_path)

    assert {p.name for p in written} == {"Code.gs", "index.html", "appsscript.json"}
    assert (tmp_path / "Code.gs").read_text() == "function main() {}"
    assert (tmp_path / "index.html").read_text() == "<p>hi</p>"
    assert (tmp_path / "appsscript.json").read_text() == "{}"


def test_write_script_files_creates_out_dir(tmp_path: Path) -> None:
    out_dir = tmp_path / "nested" / "project"
    files = [{"name": "Code", "type": "SERVER_JS", "source": "1;"}]

    write_script_files(files, out_dir)

    assert (out_dir / "Code.gs").exists()


def test_read_script_files_round_trips_write(tmp_path: Path) -> None:
    original = [
        {"name": "Code", "type": "SERVER_JS", "source": "function main() {}"},
        {"name": "index", "type": "HTML", "source": "<p>hi</p>"},
        {"name": "appsscript", "type": "JSON", "source": "{}"},
    ]
    write_script_files(original, tmp_path)

    found = read_script_files(tmp_path)

    assert sorted(found, key=lambda f: f["name"]) == sorted(
        original, key=lambda f: f["name"]
    )


def test_read_script_files_ignores_unrelated_files(tmp_path: Path) -> None:
    (tmp_path / "Code.gs").write_text("1;")
    (tmp_path / "README.md").write_text("not a script file")

    found = read_script_files(tmp_path)

    assert [f["name"] for f in found] == ["Code"]
