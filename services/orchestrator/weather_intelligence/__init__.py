"""The Weather Intelligence Engine (plan.md §4, §8 Phase 9).

A deterministic rule layer over the decoded hourly forecast
(weather_data.hourly_facts): it finds the best contiguous window for an
activity, compares named times of day, and frames that window per persona.
No ML, no LLM — "rules decide, the LLM only words it" (plan.md §2
principle 7) is implemented here by not involving an LLM at all, the same
choice already made for warnings, METAR and TAF.

This slice covers WIE-1/2/3/6/7 (best window, what-if, persona advisory)
for WIE-13/WIE-14's web and mobile views and /intelligence/advisory.
Forecast-change detection (WIE-9/10/11/12) is not built here — see
plan.md §8 Phase 9 for what's still open.
"""
