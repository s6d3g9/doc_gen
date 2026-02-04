from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Optional

import jwt
from passlib.context import CryptContext
import hashlib

from .settings import settings


_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _bcrypt_input(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


_WORDS = [
    # Small built-in word list (EN). Keep it stable.
    "apple",
    "arch",
    "artist",
    "atom",
    "audit",
    "autumn",
    "bamboo",
    "beacon",
    "beaver",
    "bench",
    "biscuit",
    "blade",
    "blossom",
    "bonus",
    "border",
    "breeze",
    "bridge",
    "bronze",
    "buddy",
    "buffer",
    "cactus",
    "camera",
    "canvas",
    "carbon",
    "castle",
    "casual",
    "cello",
    "cement",
    "cherry",
    "chess",
    "circuit",
    "clover",
    "coffee",
    "comet",
    "copper",
    "corner",
    "cradle",
    "crisp",
    "crystal",
    "daisy",
    "dance",
    "delta",
    "denim",
    "desert",
    "detail",
    "dolphin",
    "dragon",
    "dream",
    "drift",
    "eagle",
    "earth",
    "echo",
    "ember",
    "engine",
    "fabric",
    "falcon",
    "feather",
    "fern",
    "festival",
    "finger",
    "fossil",
    "galaxy",
    "garden",
    "gentle",
    "glacier",
    "gold",
    "guitar",
    "hammer",
    "harbor",
    "hazel",
    "helmet",
    "honey",
    "ice",
    "icon",
    "idea",
    "jacket",
    "jungle",
    "karma",
    "kernel",
    "kitten",
    "ladder",
    "lagoon",
    "laser",
    "leaf",
    "lemon",
    "linen",
    "lotus",
    "lucky",
    "lunar",
    "magnet",
    "marble",
    "matrix",
    "meadow",
    "melon",
    "meteor",
    "mint",
    "mirror",
    "model",
    "monkey",
    "mosaic",
    "mountain",
    "museum",
    "myth",
    "nectar",
    "needle",
    "nebula",
    "night",
    "north",
    "nova",
    "oasis",
    "ocean",
    "olive",
    "opal",
    "orbit",
    "origin",
    "oxygen",
    "panda",
    "paper",
    "pearl",
    "pepper",
    "piano",
    "pixel",
    "planet",
    "plasma",
    "plume",
    "pocket",
    "pollen",
    "pond",
    "prairie",
    "prism",
    "pulse",
    "quartz",
    "quiet",
    "radar",
    "rain",
    "raven",
    "reef",
    "river",
    "robot",
    "rocket",
    "rose",
    "saffron",
    "sail",
    "scale",
    "scarlet",
    "shadow",
    "signal",
    "silver",
    "sketch",
    "snow",
    "solar",
    "sparrow",
    "spice",
    "spider",
    "spring",
    "stone",
    "storm",
    "sunset",
    "swallow",
    "symbol",
    "tango",
    "temple",
    "thunder",
    "timber",
    "tulip",
    "tunnel",
    "turquoise",
    "united",
    "valley",
    "velvet",
    "violin",
    "vision",
    "vivid",
    "walnut",
    "water",
    "whisper",
    "window",
    "winter",
    "wonder",
    "yellow",
    "zebra",
 ]


@dataclass(frozen=True)
class TokenData:
    user_id: str
    email: str


def _require_auth_secrets() -> tuple[str, str]:
    jwt_secret = settings.auth_jwt_secret
    seed_secret = settings.auth_seed_secret
    if not jwt_secret:
        raise ValueError("AUTH_JWT_SECRET is not configured")
    if not seed_secret:
        raise ValueError("AUTH_SEED_SECRET is not configured")
    return jwt_secret, seed_secret


def normalize_seed(seed_phrase: str) -> str:
    return " ".join([w for w in seed_phrase.strip().lower().split() if w])


def generate_seed_phrase(words: int = 12) -> str:
    # Use a stable small list; security comes from randomness, not from wordlist size.
    return " ".join(secrets.choice(_WORDS) for _ in range(words))


def seed_key(seed_phrase: str) -> str:
    _, seed_secret = _require_auth_secrets()
    seed_norm = normalize_seed(seed_phrase)
    mac = hmac.new(seed_secret.encode("utf-8"), seed_norm.encode("utf-8"), hashlib.sha256).hexdigest()
    return mac


def hash_password(password: str) -> str:
    return _pwd.hash(_bcrypt_input(password))


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd.verify(_bcrypt_input(password), password_hash)


def hash_seed(seed_phrase: str) -> str:
    return _pwd.hash(normalize_seed(seed_phrase))


def verify_seed(seed_phrase: str, seed_hash: str) -> bool:
    return _pwd.verify(normalize_seed(seed_phrase), seed_hash)


def issue_jwt(*, user_id: str, email: str) -> str:
    jwt_secret, _ = _require_auth_secrets()
    now = int(time.time())
    exp = now + int(settings.auth_jwt_ttl_seconds or 0)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


def decode_jwt(token: str) -> Optional[TokenData]:
    try:
        jwt_secret, _ = _require_auth_secrets()
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        uid = str(payload.get("sub") or "")
        email = str(payload.get("email") or "")
        if not uid or not email:
            return None
        return TokenData(user_id=uid, email=email)
    except Exception:
        return None
