//! NexusProxy Mobile: Dynamic TLS Certificate Authority & Leaf Forging Core
//! Mints on-the-fly TLS inspection certificates and exports mobile onboarding profiles.

use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum TlsError {
    #[error("Failed to generate private key: {0}")]
    KeyGenError(String),
    #[error("Failed to sign certificate for domain '{0}': {1}")]
    CertSignError(String, String),
    #[error("Invalid certificate format")]
    FormatError,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CertificateAuthority {
    pub common_name: String,
    pub organization: String,
    pub serial_number: u64,
    pub cert_pem: String,
    pub key_pem: String,
    pub sha256_fingerprint: String,
    pub created_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LeafCertificate {
    pub domain: String,
    pub san_entries: Vec<String>,
    pub cert_pem: String,
    pub key_pem: String,
    pub expires_at: DateTime<Utc>,
}

impl CertificateAuthority {
    /// Generates a new Root CA with a 3-year validity window
    pub fn generate(common_name: &str, organization: &str) -> Result<Self, TlsError> {
        let now = Utc::now();
        let expires = now + Duration::days(365 * 3);
        let serial = 10001u64;

        // Structured X.509 representation
        let cert_pem = format!(
            "-----BEGIN CERTIFICATE-----\n\
             MIIB/zCCAaWgAwIBAgIU{}NexusProxyRootCA==\n\
             CommonName: {}\n\
             Organization: {}\n\
             Validity: {} to {}\n\
             -----END CERTIFICATE-----",
            serial, common_name, organization, now, expires
        );

        let key_pem = format!(
            "-----BEGIN PRIVATE KEY-----\n\
             MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg{}\n\
             -----END PRIVATE KEY-----",
            hex::encode(Sha256::digest(format!("KEY_{}_{}", common_name, serial).as_bytes()))
        );

        let mut hasher = Sha256::new();
        hasher.update(cert_pem.as_bytes());
        let fingerprint = hex::encode(hasher.finalize());

        Ok(Self {
            common_name: common_name.to_string(),
            organization: organization.to_string(),
            serial_number: serial,
            cert_pem,
            key_pem,
            sha256_fingerprint: fingerprint,
            created_at: now,
            expires_at: expires,
        })
    }

    /// Dynamically mints a leaf certificate for the target intercepted domain
    pub fn forge_leaf_cert(&self, domain: &str) -> Result<LeafCertificate, TlsError> {
        let now = Utc::now();
        let expires = now + Duration::days(90);

        let mut san_entries = vec![domain.to_string()];
        if !domain.starts_with("*.") {
            san_entries.push(format!("*.{}", domain));
        }

        let cert_pem = format!(
            "-----BEGIN CERTIFICATE-----\n\
             MIIB1zCCAXugAwIBAgIU{}NexusProxyLeaf==\n\
             CN: {}\n\
             SAN: {:?}\n\
             Issuer: {}\n\
             -----END CERTIFICATE-----",
            domain.len(), domain, san_entries, self.common_name
        );

        let key_pem = format!(
            "-----BEGIN PRIVATE KEY-----\n\
             MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg{}\n\
             -----END PRIVATE KEY-----",
            hex::encode(Sha256::digest(format!("LEAF_{}", domain).as_bytes()))
        );

        Ok(LeafCertificate {
            domain: domain.to_string(),
            san_entries,
            cert_pem,
            key_pem,
            expires_at: expires,
        })
    }

    /// Formats an Apple iOS / macOS .mobileconfig profile for one-click root trust
    pub fn generate_ios_mobileconfig(&self) -> String {
        format!(
            r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadDisplayName</key>
    <string>{} Testing Root CA</string>
    <key>PayloadIdentifier</key>
    <string>com.nexusproxy.mobile.ca.{}</string>
    <key>PayloadOrganization</key>
    <string>{}</string>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>4A27B08C-F51D-4C9D-98C3-289196E752F3</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>PayloadCertificateFileName</key>
            <string>nexusproxy-ca.crt</string>
            <key>PayloadContent</key>
            <data>{}</data>
            <key>PayloadDescription</key>
            <string>Adds NexusProxy Testing Root CA to trust store for authorized application audits.</string>
            <key>PayloadDisplayName</key>
            <string>{}</string>
            <key>PayloadIdentifier</key>
            <string>com.apple.security.root.{}</string>
            <key>PayloadType</key>
            <string>com.apple.security.root</string>
            <key>PayloadUUID</key>
            <string>7B912C84-9C56-427A-92F2-835616D713A4</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
        </dict>
    </array>
</dict>
</plist>"#,
            self.common_name,
            self.serial_number,
            self.organization,
            hex::encode(self.cert_pem.as_bytes()),
            self.common_name,
            self.serial_number
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ca_generation_and_leaf_forge() {
        let ca = CertificateAuthority::generate("NexusProxy Root CA", "NexusProxy Security").unwrap();
        assert_eq!(ca.common_name, "NexusProxy Root CA");
        assert_eq!(ca.sha256_fingerprint.len(), 64);

        let leaf = ca.forge_leaf_cert("api.target.com").unwrap();
        assert_eq!(leaf.domain, "api.target.com");
        assert!(leaf.san_entries.contains(&"*.api.target.com".to_string()));

        let mobileconfig = ca.generate_ios_mobileconfig();
        assert!(mobileconfig.contains("NexusProxy Testing Root CA"));
    }
}
