"""Constrained, fail-closed *real API* connectors for CIPC and Ozow staging.

CIPC: subscription details vary; the subscribed endpoint and schema must be confirmed in APIVerse.
Ozow: One API STAGING ONLY, with server-side authenticated transaction polling.
No connector returns 'bank settled' or 'guaranteed legitimate supplier'.
"""
from __future__ import annotations
import os
import re
from urllib.parse import urlsplit
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import datetime as dt
import httpx

# Tests replace this transport with a deterministic in-process fake HTTP server.
HTTP_TRANSPORT = None
OZOW_STAGING = "https://stagingone.ozow.com/v1"

class ConnectorError(Exception):
    pass

def _request(method, url, **kwargs):
    try:
        with httpx.Client(timeout=12.0, follow_redirects=False, transport=HTTP_TRANSPORT) as client:
            r = client.request(method, url, **kwargs)
            if r.status_code not in range(200,300):
                raise ConnectorError(f"Provider returned HTTP {r.status_code}; check credentials and access")
            return r.json()
    except ConnectorError:
        raise
    except (httpx.RequestError, ValueError, TypeError) as exc:
        raise ConnectorError('Provider unavailable or invalid response') from exc

def ozow_configured():
    return all(os.getenv(k) for k in ('FF_OZOW_CLIENT_ID','FF_OZOW_CLIENT_SECRET','FF_OZOW_SITE_CODE','FF_OZOW_RETURN_URL'))

def _ozow_token():
    if not ozow_configured():
        raise ConnectorError('Ozow staging credentials or HTTPS return URL are not configured')
    if not os.getenv('FF_OZOW_RETURN_URL','').startswith('https://'):
        raise ConnectorError('Ozow return URL must use publicly reachable HTTPS')
    res=_request('POST',f'{OZOW_STAGING}/token',data={
        'client_id':os.environ['FF_OZOW_CLIENT_ID'],
        'client_secret':os.environ['FF_OZOW_CLIENT_SECRET'],
        'scope':'payments','grant_type':'client_credentials'})
    token=res.get('access_token') if isinstance(res,dict) else None
    if not isinstance(token,str) or not token:
        raise ConnectorError('Ozow token missing')
    return token

def ozow_create_payment(reference:str,amount_cents:int,idempotency_key:str):
    if not re.fullmatch(r'[A-Za-z0-9_-]{3,50}',reference):
        raise ConnectorError('Merchant reference must be 3-50 safe characters')
    token=_ozow_token()
    amount=float((Decimal(amount_cents)/Decimal(100)).quantize(Decimal('.01')))
    expiry=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=30)).isoformat(timespec='seconds').replace('+00:00','Z')
    res=_request('POST', f'{OZOW_STAGING}/payments',
                 headers={'Authorization':f'Bearer {token}','Idempotency-Key':idempotency_key},
                 json={'siteCode':os.environ['FF_OZOW_SITE_CODE'],
                       'amount':{'currency':'ZAR','value':amount},
                       'merchantReference':reference,'beneficiaryReference':'FRAUDFENCE',
                       'expireAt':expiry,'returnUrl':os.environ['FF_OZOW_RETURN_URL']})
    if not isinstance(res,dict) or not isinstance(res.get('id'),str):
        raise ConnectorError('Ozow did not supply a payment ID')
    redirect=res.get('redirectUrl')
    if not isinstance(redirect,str):
        raise ConnectorError('Ozow did not supply a checkout URL')
    host=urlsplit(redirect)
    if host.scheme!='https' or host.hostname not in ('stagingpay.ozow.com','stagingone.ozow.com'):
        raise ConnectorError('Ozow staging returned an unrecognised checkout URL')
    return {'payment_id':res['id'],'checkout_url':redirect,'provider_status':res.get('status','Created')}

def ozow_list_transactions(payment_id:str):
    # Never permit user input to select an API path or destination.
    if not re.fullmatch(r'[a-fA-F0-9-]{36}',payment_id):
        raise ConnectorError('Invalid provider payment identifier')
    token=_ozow_token()
    res=_request('GET',f'{OZOW_STAGING}/payments/{payment_id}/transactions',
                 headers={'Authorization':f'Bearer {token}'})
    if not isinstance(res,dict) or not isinstance(res.get('results'),list):
        raise ConnectorError('Unexpected Ozow transactions response')
    # Fail closed if paginated, rather than risk making a decision on partial evidence.
    meta=res.get('meta') or {}
    if isinstance(meta,dict) and int(meta.get('totalPages',1))>1:
        raise ConnectorError('Ozow transactions paginated; manual review required')
    return res['results']

def assess_ozow_transactions(transactions, reference, amount_cents, site_code):
    """Return payment evidence state. Treat every ambiguous or inconsistent event as HOLD."""
    if not isinstance(transactions,list):
        return 'HOLD_INVALID_PROVIDER_DATA',None
    successes=[]
    for t in transactions:
        if not isinstance(t,dict):
            return 'HOLD_INVALID_PROVIDER_DATA',None
        status=str(t.get('status','')).lower()
        if status=='refunded':
            return 'HOLD_REFUNDED',None
        if status=='successful':
            if not t.get('id') or t.get('merchantReference')!=reference or t.get('siteCode')!=site_code:
                return 'HOLD_PROVIDER_MISMATCH',None
            amount=t.get('amount',{})
            if not isinstance(amount,dict) or amount.get('currency')!='ZAR':
                return 'HOLD_PROVIDER_MISMATCH',None
            try:
                actual=(Decimal(str(amount['value']))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
            except (InvalidOperation,ValueError,KeyError):
                return 'HOLD_INVALID_PROVIDER_DATA',None
            if actual!=Decimal(amount_cents):
                return 'HOLD_PROVIDER_MISMATCH',None
            successes.append(str(t['id']))
    if len(successes)>1:
        return 'HOLD_MULTIPLE_SUCCESSFUL_TRANSACTIONS',None
    if len(successes)==1:
        return 'OZOW_STAGING_PROVIDER_CONFIRMED',successes[0]
    if any(str(t.get('status','')).lower() in ('incomplete','pending','created') for t in transactions):
        return 'OZOW_STAGING_PENDING',None
    return ('OZOW_STAGING_NOT_PAID' if transactions else 'OZOW_STAGING_PENDING'),None

def cipc_configured():
    return all(os.getenv(k) for k in ('FF_CIPC_TOKEN_URL','FF_CIPC_COMPANY_ENDPOINT','FF_CIPC_CLIENT_ID','FF_CIPC_CLIENT_SECRET','FF_CIPC_ALLOWED_HOST'))

def _cipc_guard(url:str, allow_key='FF_CIPC_ALLOWED_HOST'):
    parsed=urlsplit(url)
    allow=os.getenv(allow_key,'').strip().lower()
    if parsed.scheme!='https' or parsed.hostname!=allow or parsed.username or parsed.password or parsed.port:
        raise ConnectorError('CIPC endpoint must match the subscribed HTTPS API host')

def cipc_company_lookup(registration:str,expected_name:str):
    """Uses exact APIVerse URLs *provided by an actual subscription*; no guessed URLs or scraping."""
    if not cipc_configured():
        raise ConnectorError('CIPC APIVerse subscription endpoints and OAuth credentials not configured')
    if not re.fullmatch(r'[A-Za-z0-9/-]{4,40}',registration):
        raise ConnectorError('Invalid company registration')
    token_url=os.environ['FF_CIPC_TOKEN_URL']
    endpoint=os.environ['FF_CIPC_COMPANY_ENDPOINT']
    _cipc_guard(token_url, 'FF_CIPC_TOKEN_ALLOWED_HOST' if os.getenv('FF_CIPC_TOKEN_ALLOWED_HOST') else 'FF_CIPC_ALLOWED_HOST')
    _cipc_guard(endpoint)
    token_resp=_request('POST',token_url,data={'grant_type':'client_credentials',
                          'client_id':os.environ['FF_CIPC_CLIENT_ID'],
                          'client_secret':os.environ['FF_CIPC_CLIENT_SECRET']})
    token=token_resp.get('access_token') if isinstance(token_resp,dict) else None
    if not token:
        raise ConnectorError('CIPC OAuth token missing')
    headers={'Authorization':f'Bearer {token}'}
    if os.getenv('FF_CIPC_SUBSCRIPTION_KEY'):
        headers['Ocp-Apim-Subscription-Key']=os.environ['FF_CIPC_SUBSCRIPTION_KEY']
    # The subscription determines which parameter name is actually supported.
    res=_request('GET',endpoint,headers=headers,params={os.getenv('FF_CIPC_REG_PARAM','registrationNumber'):registration})
    if not isinstance(res,dict):
        raise ConnectorError('CIPC response is not an object')
    # Never infer a verified result from an unknown schema.
    number=res.get('registrationNumber',res.get('enterpriseNumber'))
    name=res.get('enterpriseName',res.get('registeredName'))
    status=res.get('enterpriseStatus',res.get('status'))
    fields_available=all(isinstance(v,str) and v.strip() for v in (number,name,status))
    if not fields_available:
        verdict='UNMAPPED_CIPC_SCHEMA'
    elif str(number).strip().upper()!=registration.strip().upper():
        verdict='HOLD_REGISTRATION_MISMATCH'
    elif re.sub(r'[^a-z0-9]','',name.lower())!=re.sub(r'[^a-z0-9]','',expected_name.lower()):
        verdict='HOLD_NAME_MISMATCH'
    elif status.strip().upper() not in ('ACTIVE','IN BUSINESS','IN BUSINESS AND TRADING'):
        verdict='HOLD_STATUS_REVIEW'
    else:
        verdict='CIPC_COMPANY_DETAILS_MATCH_ONLY'
    return {'source':'CIPC_AUTHENTICATED_API','verdict':verdict,
            'company_status':status if fields_available else 'UNKNOWN',
            'matched_registration':bool(fields_available and number.strip().upper()==registration.strip().upper()),
            'available_fields':list(res.keys())[:20],
            'limitation':'CIPC data does not establish authority of invoice sender, bank account ownership, or director history.'}
