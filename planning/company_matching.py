"""Match registration company names to corporate sales companies."""
from __future__ import annotations

import re

SUFFIXES = {'pte', 'ltd', 'limited', 'private', 'inc', 'llp', 'llc', 'co', 'corp', 'corporation',
    'company', 'sdn', 'bhd', 'berhad', 'plc'}


def normalize_company(name):
    """Casefold, drop bracketed notes, punctuation and trailing legal suffixes: 'Siemens Pte Ltd (Sharon)' -> 'siemens'."""
    text = re.sub(r'\([^)]*\)|\[[^\]]*\]', ' ', str(name).casefold())
    words = re.sub(r'[^0-9a-z]+', ' ', text).split()
    while words and words[-1] in SUFFIXES:
        words.pop()
    return ' '.join(words)


def link_registration_names(companies, registration_names):
    """Return {registration name: (company id, 'linked' | 'auto')}.

    'linked' = saved alias (case-insensitive). 'auto' = normalized name equals exactly one
    company's normalized name or alias; ambiguous or unmatched names are left out.
    """
    explicit = {alias.casefold(): company['id'] for company in companies for alias in company['aliases']}
    owners = {}
    for company in companies:
        for label in [company['name'], *company['aliases']]:
            key = normalize_company(label)
            if key:
                owners.setdefault(key, set()).add(company['id'])
    links = {}
    for name in registration_names:
        if name.casefold() in explicit:
            links[name] = (explicit[name.casefold()], 'linked')
            continue
        candidates = owners.get(normalize_company(name), set())
        if len(candidates) == 1:
            links[name] = (next(iter(candidates)), 'auto')
    return links
