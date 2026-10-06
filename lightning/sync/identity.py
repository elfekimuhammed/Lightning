"""This device's identity for pairing (multiple devices, task 09).

One ECDSA P-256 key per device: it signs the TLS certificate the phone serves and the challenges a PC
answers. Kept in app-private storage, readable by this user only. It is not the ledger's data key, which stays
wrapped by passwords. Later: protect it with the Android Keystore and Windows DPAPI (plan section 4).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import socket
import uuid
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from .domain import _name

PAIRING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I, O, 0 or 1 to misread
PAIRING_CODE_LENGTH = 12                                 # 60 bits, typed as three groups of four
DEFAULT_PORT = 47513


@dataclass(frozen=True)
class DeviceIdentity:
    device_id: str
    name: str
    key_path: Path
    cert_path: Path

    def _key(self) -> ec.EllipticCurvePrivateKey:
        return serialization.load_pem_private_key(self.key_path.read_bytes(), password=None)

    @property
    def certificate_der(self) -> bytes:
        return x509.load_pem_x509_certificate(self.cert_path.read_bytes()).public_bytes(serialization.Encoding.DER)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.certificate_der).hexdigest()

    @property
    def public_key(self) -> str:
        """The public key as a compressed point in hex, given to the home at pairing."""
        return self._key().public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint).hex()

    def sign(self, data: bytes) -> str:
        return self._key().sign(data, ec.ECDSA(hashes.SHA256())).hex()


def verify_signature(public_key: str, data: bytes, signature_hex: str) -> bool:
    try:
        key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), bytes.fromhex(public_key))
        key.verify(bytes.fromhex(signature_hex), data, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _write_private(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def load_or_create(folder: str | Path, name: str) -> DeviceIdentity:
    """This device's identity, created once. The name is what the other device shows ("Office PC")."""
    _name(name, "device name")
    folder = Path(folder)
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    meta, key_path, cert_path = folder / "device.json", folder / "device-key.pem", folder / "device-cert.pem"
    if meta.exists():
        record = json.loads(meta.read_text(encoding="utf-8"))
        identity = DeviceIdentity(record["device_id"], record["name"], key_path, cert_path)
        if record["name"] != name:
            meta.write_text(json.dumps({"device_id": identity.device_id, "name": name}), encoding="utf-8")
            identity = DeviceIdentity(identity.device_id, name, key_path, cert_path)
        return identity
    for stale in (key_path, cert_path):
        stale.unlink(missing_ok=True)  # an interrupted first run left no device.json: start again
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Lightning device")])
    now = dt.datetime.now(dt.timezone.utc)
    certificate = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
                   .public_key(key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=365 * 30))
                   .sign(key, hashes.SHA256()))
    _write_private(key_path, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
    _write_private(cert_path, certificate.public_bytes(serialization.Encoding.PEM))
    device_id = str(uuid.uuid4())
    _write_private(meta, json.dumps({"device_id": device_id, "name": name}).encode("utf-8"))
    return DeviceIdentity(device_id, name, key_path, cert_path)


# ------------------------------------------------------------ pairing secrets and proofs

def new_pairing_code() -> str:
    return "".join(secrets.choice(PAIRING_ALPHABET) for _ in range(PAIRING_CODE_LENGTH))


def normalize_code(text: str) -> str:
    code = "".join(ch for ch in str(text).upper() if not ch.isspace() and ch != "-")
    if len(code) != PAIRING_CODE_LENGTH or any(ch not in PAIRING_ALPHABET for ch in code):
        raise ValueError("Type the 12 letters and digits shown on the phone.")
    return code


def show_code(code: str) -> str:
    return "-".join(code[i:i + 4] for i in range(0, len(code), 4))


def transcript(pairing_id: str, home_fingerprint: str, device_id: str, public_key: str) -> bytes:
    """What both sides bind their proofs to: a relay presenting another certificate cannot match it."""
    return "\n".join(("lightning-pair-v1", pairing_id, home_fingerprint, device_id, public_key)).encode("ascii")


def proof(code: str, role: str, data: bytes) -> str:
    return hmac.new(normalize_code(code).encode("ascii"), role.encode("ascii") + b"\n" + data,
                    hashlib.sha256).hexdigest()


def check_digits(data: bytes) -> str:
    """Six digits both screens show; they match only if both devices saw the same certificate and request."""
    return f"{int.from_bytes(hashlib.sha256(b'digits' + data).digest()[:8], 'big') % 1_000_000:06d}"


def local_address() -> str:
    """This device's address on the local network, for the pairing screen. No packet is sent."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))  # TEST-NET: only selects the outgoing interface
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()
