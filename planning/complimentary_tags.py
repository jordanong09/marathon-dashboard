"""Capture complimentary tags found in registration uploads as saved programmes."""
from __future__ import annotations

import copy
import uuid

AUTO_NOTE = 'Added automatically from a registration upload'


def absorb_new_tags(programmes, tags, make_id=lambda: uuid.uuid4().hex):
    """Return (programmes, added, attached) with every unseen tag saved.

    A tag already linked (case-insensitive) is ignored. A tag equal to an existing programme's
    name is attached to that programme; any other new tag becomes its own programme.
    Existing programmes and links are never removed.
    """
    programmes = copy.deepcopy(programmes)
    linked = {tag.casefold() for programme in programmes for tag in programme['tags']}
    by_name = {programme['name'].strip().casefold(): programme for programme in programmes}
    added, attached = [], []
    for tag in dict.fromkeys(str(t).strip() for t in tags if t is not None and str(t).strip()):
        key = tag.casefold()
        if key in linked:
            continue
        if key in by_name:
            by_name[key]['tags'].append(tag)
            attached.append(tag)
        else:
            programme = {'id': make_id(), 'name': tag, 'tags': [tag], 'notes': AUTO_NOTE}
            programmes.append(programme)
            by_name[key] = programme
            added.append(tag)
        linked.add(key)
    return programmes, added, attached
