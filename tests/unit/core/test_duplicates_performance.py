"""Duplicate detection skips non-references and compares only plausible
pairs (Issue #430)."""

import random
from difflib import SequenceMatcher
from unittest.mock import MagicMock, patch

from zotero_cli.core.services.duplicate_service import DuplicateFinder
from zotero_cli.core.zotero_item import ZoteroItem


def _brute_force_pairs(titles, years, sigs):
    """The pairs the old nested loops compared titles for."""
    n = len(titles)
    return [
        (i, j)
        for i in range(n)
        for j in range(i + 1, n)
        if titles[i] and titles[j]
        and years[i] is not None and years[j] is not None
        and abs(years[i] - years[j]) <= 1
        and sigs[i] & sigs[j]
    ]


def test_blocked_candidates_equal_the_old_pairs_in_the_same_order():
    rnd = random.Random(430)
    pool = [f"author{k} a" for k in range(25)]
    for _ in range(20):
        n = rnd.randint(0, 150)
        titles = [None if rnd.random() < 0.1 else f"t{rnd.randint(0, 5)}" for _ in range(n)]
        years = [None if rnd.random() < 0.1 else rnd.randint(2000, 2006) for _ in range(n)]
        sigs = [set(rnd.sample(pool, rnd.randint(0, 3))) for _ in range(n)]
        assert DuplicateFinder._fuzzy_candidates(titles, years, sigs) == _brute_force_pairs(
            titles, years, sigs
        )


def _item(key, title, year, last, item_type="journalArticle", **extra):
    return ZoteroItem.from_raw_zotero_item(
        {
            "key": key,
            "version": 1,
            "data": {
                "itemType": item_type,
                "title": title,
                "date": str(year),
                "creators": [{"creatorType": "author", "lastName": last, "firstName": "Ann"}],
                **extra,
            },
        }
    )


def _similarity(_self, a, b):
    return SequenceMatcher(None, a, b).ratio()


def test_fuzzy_groups_are_found_without_comparing_every_pair():
    items = [(_item(f"K{n}", f"Unrelated study number {n}", 2000 + n % 20, f"author{n}"), "C")
             for n in range(2000)]
    items += [
        (_item("DUP1", "Deep learning for screening", 2020, "smith"), "C"),
        (_item("DUP2", "Deep learning for the screening", 2021, "smith"), "C"),
    ]
    finder = DuplicateFinder(MagicMock())
    with patch.object(
        DuplicateFinder, "_title_similarity", autospec=True, side_effect=_similarity
    ) as similarity:
        groups = finder._fuzzy_fallback_groups(items)

    assert [sorted(o.key for o in g.occurrences) for g in groups] == [["DUP1", "DUP2"]]
    assert similarity.call_count < 10  # only same-author pairs a year apart at most


def test_library_mode_ignores_attachments_and_notes():
    """3,502 'Full Text PDF' attachments came out as one duplicate group."""
    gateway = MagicMock()
    pdfs = [
        ZoteroItem.from_raw_zotero_item(
            {"key": f"A{n}", "version": 1,
             "data": {"itemType": "attachment", "title": "Full Text PDF", "parentItem": f"P{n}"}}
        )
        for n in range(5)
    ]
    notes = [
        ZoteroItem.from_raw_zotero_item(
            {"key": f"N{n}", "version": 1, "data": {"itemType": "note", "note": "same"}}
        )
        for n in range(3)
    ]
    gateway.get_all_items.return_value = iter(pdfs + notes + [_item("P1", "A paper", 2020, "x")])

    assert DuplicateFinder(gateway).compare_collections(None) == []
