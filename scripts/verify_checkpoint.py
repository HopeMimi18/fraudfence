"""Offline signature verifier for a downloaded signed audit checkpoint.
Usage: python -m scripts.verify_checkpoint /outside-the-app/checkpoint.json
Never fetch the verification key from the compromised server when validating history;
use a fingerprint/public key obtained from an independent trusted source.
"""
import base64
import json
import sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fraudfence.core import canonical

def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python -m scripts.verify_checkpoint checkpoint.json')
    body=json.loads(Path(sys.argv[1]).read_text())
    checkpoint=body['checkpoint'];signature=base64.b64decode(body['signature'])
    pub=Ed25519PublicKey.from_public_bytes(base64.b64decode(body['public_key']))
    pub.verify(signature,canonical(checkpoint).encode())
    print('CHECKPOINT SIGNATURE VALID')
    print('Audit index:',checkpoint['audit_id'])
    print('Expected audit hash:',checkpoint['audit_hash'])
    print('Warning: signature validity alone does not prove the signer was uncompromised.')

if __name__=='__main__':
    main()
