import warnings
import bcrypt as _bcrypt_module
from passlib.handlers import bcrypt as passlib_bcrypt

try:
    _original_hashpw = _bcrypt_module.hashpw
    
    def _patched_hashpw(password, salt):
        if isinstance(password, bytes) and len(password) > 72:
            password = password[:72]
        return _original_hashpw(password, salt)
    
    _bcrypt_module.hashpw = _patched_hashpw
    
    if hasattr(passlib_bcrypt, '_bcrypt'):
        passlib_bcrypt._bcrypt.hashpw = _patched_hashpw
    
    if hasattr(passlib_bcrypt, 'detect_wrap_bug'):
        original_detect_wrap_bug = passlib_bcrypt.detect_wrap_bug
        
        def patched_detect_wrap_bug(ident):
            try:
                return original_detect_wrap_bug(ident)
            except ValueError:
                return False
        
        passlib_bcrypt.detect_wrap_bug = patched_detect_wrap_bug
except (ImportError, AttributeError):
    pass

from passlib.context import CryptContext

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    pwd_context = CryptContext(
        schemes=["bcrypt"],
        deprecated="auto",
        bcrypt__rounds=12
    )

MAX_PASSWORD_BYTES = 72

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

PASSWORD_REQUIREMENTS = [
    (lambda p: len(p) >= 8, "Password must be at least 8 characters long"),
    (lambda p: len(p.encode('utf-8')) <= MAX_PASSWORD_BYTES, f"Password cannot be longer than {MAX_PASSWORD_BYTES} bytes"),
    (lambda p: any(c.isupper() for c in p), "Password must contain at least one uppercase letter"),
    (lambda p: any(c.islower() for c in p), "Password must contain at least one lowercase letter"),
    (lambda p: any(c.isdigit() for c in p), "Password must contain at least one number"),
    (lambda p: any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in p), "Password must contain at least one special character"),
]

def validate_password_strength(password: str) -> tuple[bool, str]:
    for requirement, error_msg in PASSWORD_REQUIREMENTS:
        if not requirement(password):
            return False, error_msg
    return True, ""
