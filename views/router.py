"""Dispatch the planning and stakeholder pages."""
from __future__ import annotations

from corporate_sales import render_corporate_sales
from views.campaigns import render_campaigns
from views.common import planning_context, reload_button, show_saved_notice, storage_banner
from views.complimentary import render_complimentary
from views.executive_summary import render_executive_summary
from views.plan_allocation import render_plan_allocation

PAGES = {
    'Executive Summary': render_executive_summary,
    'Plan Allocation': render_plan_allocation,
    'Corporate Sales': render_corporate_sales,
    'Complimentary': render_complimentary,
    'Campaigns': render_campaigns,
}
PLANNING_PAGES = tuple(PAGES)


def render_planning_page(page, data, promo_column):
    storage_banner()
    show_saved_notice()
    ctx = planning_context(data, promo_column)
    if ctx is None:
        return
    reload_button('reload_' + page)
    PAGES[page](ctx)
