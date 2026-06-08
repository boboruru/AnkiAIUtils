import urllib.request
from typing import Dict
import json
from py_ankiconnect import PyAnkiconnect

anki = PyAnkiconnect(default_port=8766)

def sync_anki() -> None:
    "trigger anki synchronization"
    sync_output = anki(action="sync")
    assert (
        sync_output is None or sync_output == "None"
    ), f"Error during sync?: '{sync_output}'"


def addtags(nid: int, tags: str) -> None:
    assert isinstance(nid, (int, str))
    assert isinstance(tags, str)
    out = anki(
        action="addTags",
        notes=[int(nid)],
        tags=tags,
    )
    assert out == "None" or out is None, f"Exception when adding '{tags}' to note: {nid}"


def removetags(nid: int, tags: str) -> None:
    assert isinstance(nid, (int, str))
    assert isinstance(tags, str)
    out = anki(
        action="removeTags",
        notes=[int(nid)],
        tags=tags,
    )
    assert out == "None" or out is None, f"Exception when removing '{tags}' to note: {nid}"


def updatenote(nid: int, fields: Dict) -> None:
    assert isinstance(nid, (int, str))
    assert isinstance(fields, dict)
    out = anki(
        action="updateNoteFields",
        note={
            "id": int(nid),
            "fields": fields,
        },
    )
    assert (
        out == "None" or out is None
    ), f"Exception when updating note field done tag from note: {nid} {note}"
