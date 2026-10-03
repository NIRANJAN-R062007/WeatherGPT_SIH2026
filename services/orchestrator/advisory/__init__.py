"""Travel and farming advisory engine (plan.md §8 Phase 10, §11.2a, §11.6/§11.7).

`slots.py` (TFA-3) turns a question into canonical slots; `facts.py` (TFA-4) collects
the facts both features answer from; `schema.py` and `guardrail.check_advisory` (TFA-5)
fix the answer shape and check it against those facts; `rubric.py` holds the verdict
rules and the hard override; `agent.py` (TFA-17) is the Strands agent that reads the
facts, with `template.py` as the rule-based answer when the agent is off or fails.
"""
