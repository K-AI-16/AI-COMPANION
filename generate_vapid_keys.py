"""Run once to generate VAPID keys, then add them to .env"""
from py_vapid import Vapid
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, PrivateFormat, NoEncryption
import base64

v = Vapid()
v.generate_keys()

pub = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
priv_pem = v.private_key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption())

pub_b64 = base64.urlsafe_b64encode(pub).rstrip(b'=').decode()

with open("vapid_private.pem", "wb") as f:
    f.write(priv_pem)

print("Add to backend .env:")
print(f"VAPID_PUBLIC_KEY={pub_b64}")
print(f"VAPID_PRIVATE_KEY_PATH=vapid_private.pem")
print()
print("Add to frontend/.env:")
print(f"VITE_VAPID_PUBLIC_KEY={pub_b64}")
print()
print("vapid_private.pem saved.")
