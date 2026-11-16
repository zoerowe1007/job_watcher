import pytest

from watcher.titlerule import in_role


@pytest.mark.parametrize("title", [
    "Financial Analyst",
    "Senior Financial Analyst, FP&A",
    "FP and A Lead",
    "Data Analyst II",
    "Business Intelligence Developer",
    "Credit Risk Analyst",
    "Supply Chain Analyst",
    "Sr. Analyst - Revenue Operations",
    "Marketing Analytics Associate",
    "Financial Planning Specialist",
    "BI Developer",
    "analyst, treasury",
])
def test_in_role_titles(title):
    assert in_role(title) is True


@pytest.mark.parametrize("title", [
    "Store Associate",
    "Truck Driver",
    "Registered Nurse",
    "Director, Financial Planning & Analysis",
    "Vice President, Data Analytics",
    "VP of Analytics",
    "Cybersecurity Analyst",
    "Network Analyst",
    "Software Engineer, Analytics Platform",
    "SOC Analyst",
    "QA Analyst",
    "Manager, Financial Analysis",
    "Principal Data Analyst",
    "",
    None,
])
def test_not_in_role_titles(title):
    assert in_role(title) is False


def test_analyst_must_be_a_whole_word():
    assert in_role("Psychoanalyst Assistant") is False


def test_case_is_ignored():
    assert in_role("FINANCIAL ANALYST") is True
    assert in_role("financial analyst") is True
