"""The title rule: is a posting in my role?

My role is the analyst family in finance and data: financial analyst, FP&A,
data analyst, business intelligence, credit analyst, supply chain analyst and
similar. A title is in role when it matches an INCLUDE pattern and does not
match an EXCLUDE pattern. Matching ignores case.

The rule is applied when the history is built, so changing it here changes
every day of the history the next time the history is rebuilt.
"""
import re

INCLUDE = [
    r"\banalyst\b",
    r"\banalysts\b",
    r"\banalytics\b",
    r"\bfp\s*(&|and)\s*a\b",
    r"\bfinancial planning\b",
    r"\bbusiness intelligence\b",
    r"\bbi (developer|engineer|specialist)\b",
]

EXCLUDE = [
    # senior leadership is not an analyst role
    r"\bdirector\b", r"\bvice president\b", r"\bvp\b", r"\bsvp\b", r"\bavp\b",
    r"\bhead of\b", r"\bchief\b", r"\bmanager\b", r"\bprincipal\b",
    # analysts in unrelated fields
    r"\b(cyber|cybersecurity|security|network|infrastructure|devops|software)\b",
    r"\b(nurse|nursing|clinical|pharmacist|technician|driver|mechanic)\b",
    r"\b(soc|helpdesk|help desk|qa|test)\s+analyst\b",
]

_INCLUDE = [re.compile(p, re.IGNORECASE) for p in INCLUDE]
_EXCLUDE = [re.compile(p, re.IGNORECASE) for p in EXCLUDE]


def in_role(title):
    """True when the title is in my role."""
    title = title or ""
    if not any(p.search(title) for p in _INCLUDE):
        return False
    return not any(p.search(title) for p in _EXCLUDE)
