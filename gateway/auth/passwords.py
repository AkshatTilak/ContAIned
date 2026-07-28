"""Password hashing primitives, verification, and policy enforcement (S6-03b)."""

import os
from functools import lru_cache
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from common.observability.exceptions import PasswordPolicyError

# OWASP recommended Argon2id parameters
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Constant fixture hash for dummy verification to mitigate timing side-channel attacks
_dummy_hash = _hasher.hash("dummy_constant_password_123!")


@lru_cache(maxsize=1)
def _load_common_passwords() -> frozenset[str]:
    """Load top common password denylist from common_passwords.txt."""
    file_path = os.path.join(os.path.dirname(__file__), "common_passwords.txt")
    if not os.path.exists(file_path):
        return frozenset()
    with open(file_path, "r", encoding="utf-8") as f:
        return frozenset(line.strip().lower() for line in f if line.strip())


def hash_password(plain: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _hasher.hash(plain)


def verify_password(plain: str, stored_hash: Optional[str]) -> bool:
    """Verify a plaintext password against a stored Argon2id hash.

    Runs a dummy verification against a constant fixture hash when stored_hash is None
    to ensure constant-time execution regardless of account existence.
    """
    if not stored_hash:
        try:
            _hasher.verify(_dummy_hash, plain)
        except Exception:
            pass
        return False

    try:
        return _hasher.verify(stored_hash, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    """Check if a stored password hash needs re-hashing to modern parameters."""
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except Exception:
        return True


def validate_password_policy(plain: str, email: str) -> None:
    """Validate a proposed password against complexity and safety policies.

    Raises PasswordPolicyError if any policy rules are violated.
    """
    rules: list[str] = []

    if len(plain) < 12:
        rules.append("Password must be at least 12 characters long")
    if len(plain) > 128:
        rules.append("Password must not exceed 128 characters")

    # Email local-part check
    if email and "@" in email:
        local_part = email.split("@")[0].strip().lower()
        if len(local_part) >= 3 and local_part in plain.lower():
            rules.append("Password must not contain your email username")

    # Denylist check
    denylist = _load_common_passwords()
    if plain.lower().strip() in denylist:
        rules.append("Password is too common and easily guessable")

    if rules:
        raise PasswordPolicyError(
            message="Password does not meet policy requirements",
            details={"rules": rules},
        )
