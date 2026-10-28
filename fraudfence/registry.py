"""Read-only fictional CIPC-style adapter for local security demonstrations.

This module does NOT contact CIPC, BizPortal, or any live government service.
It checks user-submitted identifiers against a fixed, independently held local
fixture, rather than trusting the invoice to attest its own company identity.
"""
from __future__ import annotations
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class DemoCompany:
    legal_name: str
    status: str
    recent_director_change: bool = False


# Entirely fictional companies and registration identifiers.
MOCK_COMPANIES = {
    'DEMO-REG-001': DemoCompany('BuildRite Demo Supplies Pty Ltd', 'ACTIVE'),
    'DEMO-REG-002': DemoCompany('Ubuntu Office Demo Trading Pty Ltd', 'ACTIVE'),
    'DEMO-REG-003': DemoCompany('Cedar Distribution Demo Pty Ltd', 'ACTIVE', recent_director_change=True),
    'DEMO-REG-004': DemoCompany('Inactive Demo Traders Pty Ltd', 'DEREGISTERED'),
    # Pitch scenario: once-trusted supplier now has a recent fictional director change.
    'DEMO-PITCH-BUILDRITE': DemoCompany('BuildRite Supplies (Pty) Ltd', 'ACTIVE', recent_director_change=True),
}


def norm_name(value: str) -> str:
    # Demo-friendly comparison. Real entity resolution requires a contracted
    # authoritative provider and careful legal-name normalization.
    return re.sub(r'[^a-z0-9]', '', value.lower())


def check_registry(registration: str, expected_legal_name: str,
                   identity_source: str, demo_mode: bool) -> dict:
    """Return a narrow evidence result; never a general 'safe supplier' claim."""
    if not demo_mode:
        return {'result': 'UNAVAILABLE', 'provider': 'NOT_CONNECTED', 'company_status': 'UNKNOWN',
                'recent_director_change': None}
    if identity_source != 'independent_record':
        return {'result': 'IDENTITY_NOT_ESTABLISHED', 'provider': 'MOCK_CIPC',
                'company_status': 'UNKNOWN', 'recent_director_change': None}
    company = MOCK_COMPANIES.get(registration.strip().upper())
    if company is None:
        return {'result': 'MOCK_NOT_FOUND', 'provider': 'MOCK_CIPC',
                'company_status': 'UNKNOWN', 'recent_director_change': None}
    if norm_name(company.legal_name) != norm_name(expected_legal_name):
        result = 'MOCK_NAME_MISMATCH'
    elif company.status != 'ACTIVE':
        result = 'MOCK_COMPANY_INACTIVE'
    elif company.recent_director_change:
        result = 'MOCK_RECENT_CHANGE'
    else:
        result = 'MOCK_MATCH'
    return {'result': result, 'provider': 'MOCK_CIPC',
            'company_status': company.status, 'recent_director_change': company.recent_director_change}
