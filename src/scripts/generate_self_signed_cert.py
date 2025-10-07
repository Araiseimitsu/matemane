import argparse
from datetime import datetime, timedelta
from pathlib import Path
import ipaddress

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_cert(common_name: str, days_valid: int, cert_path: Path, key_path: Path) -> None:
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    name_attributes = [
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ]
    subject = x509.Name(name_attributes)
    issuer = subject

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow() - timedelta(minutes=1))
        .not_valid_after(datetime.utcnow() + timedelta(days=days_valid))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
    )

    try:
        ip = ipaddress.ip_address(common_name)
        san = x509.SubjectAlternativeName([x509.IPAddress(ip)])
    except ValueError:
        san = x509.SubjectAlternativeName([x509.DNSName(common_name)])

    builder = builder.add_extension(san, critical=False)

    certificate = builder.sign(private_key, hashes.SHA256())

    key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_bytes = certificate.public_bytes(serialization.Encoding.PEM)

    key_path.write_bytes(key_bytes)
    cert_path.write_bytes(cert_bytes)


def main():
    parser = argparse.ArgumentParser(description="Generate self-signed PEM certificate for HTTPS")
    parser.add_argument("-n", "--cn", default="localhost", help="Common Name (hostname or IP) for the certificate")
    parser.add_argument("-d", "--days", type=int, default=365, help="Validity period in days")
    parser.add_argument("--cert", default=str(Path("instance/ssl/cert.pem")), help="Output path for cert.pem")
    parser.add_argument("--key", default=str(Path("instance/ssl/key.pem")), help="Output path for key.pem")
    args = parser.parse_args()

    cert_path = Path(args.cert)
    key_path = Path(args.key)

    generate_cert(args.cn, args.days, cert_path, key_path)

    print("=== Self-signed certificate generated ===")
    print(f"CN: {args.cn}")
    print(f"Cert: {cert_path}")
    print(f"Key:  {key_path}")
    print("----------------------------------------")
    print("Set these in .env and start the server:")
    print(f"SSL_CERTFILE={cert_path}")
    print(f"SSL_KEYFILE={key_path}")


if __name__ == "__main__":
    main()