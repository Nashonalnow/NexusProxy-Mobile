#!/usr/bin/env python3
"""
NexusProxy Mobile™ | Authentic X.509 Root CA & Dynamic Leaf Engine
RFC 5280 compliant X.509v3 Root CA and TLS certificate generator.
Strict Copper Standard: 100% authentic ASN.1 DER / PEM verifiable by OpenSSL & Mobile Trust Stores.
"""

import os
import sys
import base64
import uuid
import datetime
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

class AuthenticCAEngine:
    """
    Manages authentic X.509 Root CA lifecycle and mints leaf certificates for TLS interception.
    Adheres strictly to RFC 5280, Android Keystore CA standards, and Apple Configuration Profile specs.
    """

    def __init__(self, ca_dir: Optional[Path] = None):
        if ca_dir is not None:
            self.ca_dir = Path(ca_dir)
            self.ca_dir.mkdir(parents=True, exist_ok=True)
        else:
            # Check candidate directories in order of preference
            candidates = [
                Path(__file__).resolve().parent.parent / "ca",
                Path.home() / ".nexusproxy" / "ca",
                Path("/tmp/nexusproxy_ca")
            ]
            chosen_dir = None
            for cand in candidates:
                try:
                    cand.mkdir(parents=True, exist_ok=True)
                    # Verify write access
                    test_file = cand / ".write_test"
                    test_file.touch()
                    test_file.unlink()
                    chosen_dir = cand
                    break
                except Exception:
                    continue

            if chosen_dir is None:
                # Ultimate in-memory or /tmp fallback
                chosen_dir = Path("/tmp/nexusproxy_ca")
                chosen_dir.mkdir(parents=True, exist_ok=True)

            self.ca_dir = chosen_dir

        self.key_path = self.ca_dir / "nexusproxy-ca.key"
        self.crt_path = self.ca_dir / "nexusproxy-ca.crt"
        self.der_path = self.ca_dir / "nexusproxy-ca.der"
        self.mobileconfig_path = self.ca_dir / "nexusproxy-ca.mobileconfig"

        self.ca_key: Optional[rsa.RSAPrivateKey] = None
        self.ca_cert: Optional[x509.Certificate] = None
        self.load_or_generate()

    def load_or_generate(self) -> None:
        """Loads existing Root CA from disk or mints a new 100% authentic Root CA."""
        if self.key_path.exists() and self.crt_path.exists():
            try:
                key_bytes = self.key_path.read_bytes()
                crt_bytes = self.crt_path.read_bytes()
                self.ca_key = serialization.load_pem_private_key(key_bytes, password=None)
                self.ca_cert = x509.load_pem_x509_certificate(crt_bytes)
                # Ensure DER and mobileconfig exist
                if not self.der_path.exists():
                    self.der_path.write_bytes(self.ca_cert.public_bytes(serialization.Encoding.DER))
                if not self.mobileconfig_path.exists():
                    self.mobileconfig_path.write_text(self._generate_apple_profile_xml(), encoding="utf-8")
                return
            except Exception as e:
                print(f"[CAEngine] Existing CA invalid or corrupted ({e}), regenerating...", file=sys.stderr)

        self.generate_new_root_ca()

    def generate_new_root_ca(
        self,
        common_name: str = "NexusProxy Testing Root CA",
        organization: str = "NexusProxy Mobile Security",
        organizational_unit: str = "Security Operations",
        validity_days: int = 1825  # 5 years
    ) -> None:
        """
        Mints a genuine RFC 5280 X.509v3 Root CA using RSA-2048.
        Critical extensions: BasicConstraints(ca=True), KeyUsage(keyCertSign, cRLSign).
        """
        # Generate private key
        self.ca_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, organizational_unit),
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        ])

        now = datetime.datetime.now(datetime.timezone.utc)
        expires = now + datetime.timedelta(days=validity_days)
        serial = x509.random_serial_number()

        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(self.ca_key.public_key())
            .serial_number(serial)
            .not_valid_before(now)
            .not_valid_after(expires)
            # CA:TRUE constraint (marked critical) - required by Android 11+ & iOS
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            # Key usage for Root CA (marked critical)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            # Subject Key Identifier
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(self.ca_key.public_key()),
                critical=False,
            )
            # Authority Key Identifier
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(self.ca_key.public_key()),
                critical=False,
            )
        )

        self.ca_cert = builder.sign(
            private_key=self.ca_key,
            algorithm=hashes.SHA256()
        )

        # Persist private key (PEM, 0600)
        pem_key = self.ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
        self.key_path.write_bytes(pem_key)
        try:
            os.chmod(self.key_path, 0o600)
        except OSError:
            pass

        # Persist PEM certificate (.crt)
        pem_crt = self.ca_cert.public_bytes(serialization.Encoding.PEM)
        self.crt_path.write_bytes(pem_crt)

        # Persist DER certificate (.der)
        der_crt = self.ca_cert.public_bytes(serialization.Encoding.DER)
        self.der_path.write_bytes(der_crt)

        # Persist Apple .mobileconfig
        mobileconfig_xml = self._generate_apple_profile_xml()
        self.mobileconfig_path.write_text(mobileconfig_xml, encoding="utf-8")

    def _generate_apple_profile_xml(self) -> str:
        """
        Constructs an authentic Apple Configuration Profile XML (.mobileconfig)
        with the Root CA DER certificate Base64-encoded inside <data>.
        """
        if not self.ca_cert:
            return ""

        der_bytes = self.ca_cert.public_bytes(serialization.Encoding.DER)
        b64_payload = base64.b64encode(der_bytes).decode("ascii")
        # Split into standard 64-char lines for clean plist XML
        formatted_b64 = "\n\t\t\t\t" + "\n\t\t\t\t".join(
            b64_payload[i:i+64] for i in range(0, len(b64_payload), 64)
        ) + "\n\t\t\t"

        profile_uuid = str(uuid.uuid4()).upper()
        payload_uuid = str(uuid.uuid4()).upper()

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>PayloadDisplayName</key>
	<string>NexusProxy Testing Root CA</string>
	<key>PayloadDescription</key>
	<string>Installs NexusProxy Mobile Root Certificate Authority for authorized mobile security testing and HTTP/S traffic inspection.</string>
	<key>PayloadIdentifier</key>
	<string>com.nexusproxy.mobile.ca.profile</string>
	<key>PayloadOrganization</key>
	<string>NexusProxy Mobile Security</string>
	<key>PayloadType</key>
	<string>Configuration</string>
	<key>PayloadUUID</key>
	<string>{profile_uuid}</string>
	<key>PayloadVersion</key>
	<integer>1</integer>
	<key>PayloadScope</key>
	<string>User</string>
	<key>PayloadContent</key>
	<array>
		<dict>
			<key>PayloadCertificateFileName</key>
			<string>nexusproxy-ca.crt</string>
			<key>PayloadContent</key>
			<data>{formatted_b64}</data>
			<key>PayloadDescription</key>
			<string>NexusProxy Root Certificate Authority for TLS inspection.</string>
			<key>PayloadDisplayName</key>
			<string>NexusProxy Testing Root CA</string>
			<key>PayloadIdentifier</key>
			<string>com.apple.security.root.{payload_uuid}</string>
			<key>PayloadType</key>
			<string>com.apple.security.root</string>
			<key>PayloadUUID</key>
			<string>{payload_uuid}</string>
			<key>PayloadVersion</key>
			<integer>1</integer>
		</dict>
	</array>
</dict>
</plist>"""

    def get_pem_certificate(self) -> str:
        """Returns the authentic Root CA public certificate in PEM format."""
        if not self.ca_cert:
            return ""
        return self.ca_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")

    def get_der_certificate(self) -> bytes:
        """Returns the authentic Root CA public certificate in binary DER format."""
        if not self.ca_cert:
            return b""
        return self.ca_cert.public_bytes(serialization.Encoding.DER)

    def get_mobileconfig_xml(self) -> str:
        """Returns Apple .mobileconfig profile string."""
        if self.mobileconfig_path.exists():
            return self.mobileconfig_path.read_text(encoding="utf-8")
        return self._generate_apple_profile_xml()

    def get_fingerprint_sha256(self) -> str:
        """Returns genuine SHA-256 fingerprint of the Root CA certificate."""
        if not self.ca_cert:
            return "UNAVAILABLE"
        return self.ca_cert.fingerprint(hashes.SHA256()).hex().lower()

    def get_details(self) -> Dict[str, Any]:
        """Returns comprehensive cryptographic details of the Root CA."""
        if not self.ca_cert:
            return {}

        now = datetime.datetime.now(datetime.timezone.utc)
        valid_until = self.ca_cert.not_valid_after_utc
        days_remaining = (valid_until - now).days

        return {
            "common_name": "NexusProxy Testing Root CA",
            "organization": "NexusProxy Mobile Security",
            "fingerprint_sha256": self.get_fingerprint_sha256(),
            "serial_number": str(self.ca_cert.serial_number),
            "not_valid_before": self.ca_cert.not_valid_before_utc.isoformat(),
            "not_valid_after": self.ca_cert.not_valid_after_utc.isoformat(),
            "days_remaining": days_remaining,
            "validity": f"{days_remaining} days remaining (Expires {valid_until.strftime('%Y-%m-%d')})",
            "key_algorithm": "RSA-2048",
            "signature_hash_algorithm": self.ca_cert.signature_hash_algorithm.name.upper(),
            "is_ca": True,
            "pem": self.get_pem_certificate()
        }

    def mint_leaf_certificate(self, domain: str, validity_days: int = 90) -> Tuple[str, str]:
        """
        Mints an authentic X.509v3 leaf certificate signed by the Root CA for dynamic TLS interception.
        Includes SAN (Subject Alternative Name) for the specified target domain and its wildcard.
        Returns (leaf_pem_cert, leaf_pem_key).
        """
        if not self.ca_key or not self.ca_cert:
            raise RuntimeError("Root CA is not initialized")

        leaf_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )

        domain_clean = domain.strip().lower()
        alt_names = [x509.DNSName(domain_clean)]
        if not domain_clean.startswith("*."):
            alt_names.append(x509.DNSName(f"*.{domain_clean}"))

        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, domain_clean),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NexusProxy Mobile Security"),
        ])

        now = datetime.datetime.now(datetime.timezone.utc)
        expires = now + datetime.timedelta(days=validity_days)

        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self.ca_cert.subject)
            .public_key(leaf_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(expires)
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=True,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                critical=False,
            )
            .add_extension(
                x509.SubjectAlternativeName(alt_names),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(self.ca_key.public_key()),
                critical=False,
            )
        )

        leaf_cert = builder.sign(
            private_key=self.ca_key,
            algorithm=hashes.SHA256()
        )

        leaf_cert_pem = leaf_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        leaf_key_pem = leaf_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ).decode("utf-8")

        return leaf_cert_pem, leaf_key_pem

# Singleton instance
ca_engine = AuthenticCAEngine()
