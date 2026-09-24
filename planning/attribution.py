"""Assign every registration to exactly one planning group."""
from __future__ import annotations

import numpy as np
import pandas as pd

from planning.categories import to_planning_category

COLUMNS = ['Group', 'Subgroup', 'Planning Category', 'Promo Code', 'Campaign', 'Conflict', 'Other Matches']


def clean_codes(series):
    values = series.fillna('').astype(str).str.strip()
    return values.mask(values.str.lower().isin(['', 'n/a', 'na', 'nan', 'none', '<na>']), '')


def _text(data, column):
    if column not in data:
        return pd.Series('', index=data.index, dtype=object)
    return data[column].fillna('').astype(str).str.strip().astype(object)


def attribute(data, promo_column, corporate_aliases, comp_tags, campaign_codes):
    """Priority: corporate tag > complimentary tag > campaign code > retail by market.

    corporate_aliases: {registration name casefolded: company}
    comp_tags: {complimentary tag casefolded: programme}
    campaign_codes: {exact code: campaign}
    """
    if data is None or data.empty:
        return pd.DataFrame(columns=COLUMNS)
    corporate = _text(data, 'Corporate Group')
    complimentary = _text(data, 'Complimentary Programme')
    codes = clean_codes(data[promo_column]).astype(object) if promo_column else pd.Series('', index=data.index, dtype=object)
    campaign = codes.map(campaign_codes).fillna('').astype(object)
    is_corporate, is_comp, is_campaign = corporate.ne(''), complimentary.ne(''), campaign.ne('')
    local = _text(data, 'Market').eq('Singapore')
    group = np.select([is_corporate, is_comp, is_campaign, local],
        ['Corporate', 'Complimentary', 'Campaign', 'Local Retail'], 'International Retail')
    subgroup = np.select([is_corporate, is_comp, is_campaign], [
        corporate.str.casefold().map(corporate_aliases).fillna('Unlinked'),
        complimentary.str.casefold().map(comp_tags).fillna('Unconfigured'),
        campaign], '')
    comp_other = pd.Series(np.where(is_comp & is_corporate, 'Complimentary: ' + complimentary, ''), index=data.index)
    campaign_other = pd.Series(np.where(is_campaign & (is_corporate | is_comp), 'Campaign: ' + campaign, ''), index=data.index)
    other = (comp_other + '; ' + campaign_other).str.strip('; ')
    return pd.DataFrame({
        'Group': group, 'Subgroup': subgroup,
        'Planning Category': data['Grouped Category'].map(to_planning_category),
        'Promo Code': codes, 'Campaign': campaign,
        'Conflict': other.ne(''), 'Other Matches': other}, index=data.index)
