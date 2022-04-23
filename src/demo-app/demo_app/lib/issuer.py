import io
import shutil
import tempfile
import time
import weakref
from base64 import b32encode, urlsafe_b64decode, urlsafe_b64encode
from contextlib import contextmanager
from enum import Enum
from hashlib import sha256
from pathlib import Path
from subprocess import PIPE, run
from typing import Any, Dict, Iterator, List, Literal, Optional, Tuple, Union

import nkeys
from pydantic import BaseModel, BaseSettings, Field


class TempDir:
    """Temporary directory that is removed once used."""

    def __init__(self, path: Union[Path, str, None] = None):
        # Either accept a path as a string or Path
        if path:
            self.path = Path(path)
            # Manually create the directory
            self.path.mkdir(parents=False, exist_ok=False)
        # Or create a new one
        else:
            # mkdtemp handles the directory creation
            self.path = Path(tempfile.mkdtemp())
        self.name = str(self.path.resolve().absolute())
        # Register the finalizer that will remove the directory recursively
        self._finalizer = weakref.finalize(self, shutil.rmtree, self.name)

    def remove(self) -> None:
        """Remove the directory."""
        self._finalizer()

    @property
    def removed(self) -> bool:
        """Return True if the directory has been removed."""
        return not self._finalizer.alive

    def __enter__(self) -> "TempDir":
        """Allows usage with context manager:

        ```
        with TempDir() as tmpdir:
            print(tmpdir)
        ```

        Note: `tmpdir` object will still exist but directory will be removed.
        """
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        """Always remove the directory when exiting context manager."""
        self.remove()

    def __repr__(self) -> str:
        """Provide a user friendly string representation."""
        return f"TempDir(path='{self.path}', exists={not self.removed})"

    def __str__(self) -> str:
        """Provide a basic string representation."""
        return str(self.path)


def load_keys(
    seed: Union[str, bytes, Path, io.TextIOBase, io.BufferedIOBase, nkeys.KeyPair]
) -> nkeys.KeyPair:
    """Load nkeys"""
    if isinstance(seed, io.TextIOBase):
        seed = seed.read().encode("utf-8")
    elif isinstance(seed, io.BufferedIOBase):
        seed = seed.read()
    elif isinstance(seed, str):
        seed = seed.encode("utf-8")
    elif isinstance(seed, Path):
        seed = seed.read_bytes()
    # Parse seed into a KeyPair
    if not isinstance(seed, nkeys.KeyPair):
        return nkeys.from_seed(seed)
    # Finally nkeys.KeyPair instance
    return seed


JWT_ALG = "ed25519-nkey"


class IssuerFilesSettings(BaseSettings, case_sensitive=False):
    """Issuer settings files"""

    account_signing_key_file: Optional[str] = None
    account_public_key_file: Optional[str] = None


class IssuerSettings(BaseSettings, case_sensitive=False):
    """Issuer settings"""

    account_signing_key: Optional[str] = None
    account_public_key: Optional[str] = None


class IssuerPublicKeys(BaseModel):
    account_key: str
    signing_key: str


class IssuerConfig(BaseModel):
    account_signing_key: str
    account_public_key: Optional[str] = None

    @classmethod
    def parse(
        cls,
        account_signing_key_file: Optional[str] = None,
        account_public_key_file: Optional[str] = None,
        account_signing_key: Optional[str] = None,
        account_public_key: Optional[str] = None,
    ) -> "IssuerConfig":
        # First load files settings
        files_settings = IssuerFilesSettings()
        # Initialize empty dict
        settings_from_file: Dict[str, Any] = {}
        # Load nkeys from file
        if files_settings.account_signing_key_file:
            settings_from_file["account_signing_key"] = Path(
                files_settings.account_signing_key_file
            ).read_text()
        # Load public key from file
        if files_settings.account_public_key_file:
            settings_from_file["account_public_key"] = Path(
                files_settings.account_public_key_file
            ).read_text()
        # Create first instance of settings
        settings = IssuerSettings(**settings_from_file)
        # Create instance of settings using env values
        env_settings = IssuerSettings().dict(exclude_unset=True)
        settings = settings.copy(update=env_settings)
        # Override values using arguments when they exist
        if account_signing_key_file:
            settings.account_signing_key = Path(account_signing_key_file).read_text()
        elif account_signing_key:
            settings.account_signing_key = account_signing_key
        if account_public_key_file:
            settings.account_public_key = Path(account_public_key_file).read_text()
        elif account_public_key:
            settings.account_public_key = account_public_key
        # Check that settings.nkeys seed is not None
        if settings.account_signing_key is None:
            raise ValueError("No nkeys seed provided")
        # Return config from settings
        return cls(
            account_signing_key=settings.account_signing_key,
            account_public_key=settings.account_public_key,
        )


class Role(str, Enum):
    operator = "OPERATOR"
    account = "ACCOUNT"
    user = "USER"


class Header(BaseModel):
    """JWT Header must have algorithm set to 'ed25519-nkey'"""

    typ: str = "JWT"
    alg: str = JWT_ALG


class Permissions(BaseModel):
    """Deny or allow communication on a list of subjects"""

    deny: Optional[List[str]] = None
    allow: Optional[List[str]] = None


class NATSAttrs(BaseModel):
    """NATS metadata and permissions found in payload"""

    data: int = Field(
        -1,
        description="set maximum data in bytes for the user (-1 is unlimited) (default -1)",
    )
    payload: int = Field(
        -1,
        description="set maximum message payload in bytes for the account (-1 is unlimited) (default -1)",
    )
    issuer_account: Optional[str] = Field(None, description="Public key of issuer")
    pub: Permissions = Field(
        default_factory=Permissions,
        description="Allow or deny publications on subjects. By default all subjects can be published to.",
    )
    sub: Permissions = Field(
        default_factory=Permissions,
        description="Allow or deny subscriptions on subjects. By default all subjects can be subscribed to.",
    )
    subs: int = Field(
        -1,
        description="set maximum number of subscriptions (-1 is unlimited) (default -1)",
    )
    type: str = Field("user", description="Type of credentials. Must be set to user.")
    version: int = Field(2, description="JWT version. 2 by default.")

    class Config:
        schema_extra = {
            "example": {
                "data": -1,
                "payload": -1,
                "sub": {"allow": [">"]},
                "pub": {"allow": [">"]},
            }
        }


class Claims(BaseModel):
    """User claims found in JWT"""

    jti: str
    iat: int
    iss: str
    name: str
    sub: str
    nats: NATSAttrs


class JWT(BaseModel):
    """Complete JWT structure"""

    header: Header = Field(
        default_factory=Header, description="JWT Headers indicate algorithm used."
    )
    claims: Claims = Field(..., description="JWT payload holding user claims")
    signature: bytes = Field(..., description="JWT signature")

    @property
    def encoded_header(self) -> bytes:
        """Encoded header found in JWT"""
        return urlsafe_b64encode(self.header.json().encode("utf-8")).strip(b"=")

    @property
    def encoded_claims(self) -> bytes:
        """Encoded claims found in JWT"""
        return urlsafe_b64encode(
            self.claims.json(exclude_unset=True, by_alias=True).encode("utf-8")
        ).strip(b"=")

    @property
    def encoded_signature(self) -> bytes:
        """Encoded signature found in JWT"""
        return urlsafe_b64encode(self.signature).strip(b"=")

    def verify(
        self,
        seed: Union[str, bytes, Path, io.TextIOBase, io.BufferedIOBase, nkeys.KeyPair],
    ) -> Literal[True]:
        """Verify that the JWT is indeed signed by the nkeys seed"""
        # Check algorithm
        if self.header.alg != JWT_ALG:
            raise ValueError(f"Invalid algorithm: {self.header.alg}")
        # Gather signed content
        signed = b".".join([self.encoded_header, self.encoded_claims])
        # Load keypair from seed
        keypair = load_keys(seed)
        # Verify that signature is coherent and matches signing keypair
        if keypair.verify(signed, self.signature):
            return True
        # This should never happen
        raise ValueError("Failed to verify JWT")

    def encode(self) -> bytes:
        """Encode JWT as bytes"""
        return b".".join(
            [self.encoded_header, self.encoded_claims, self.encoded_signature]
        )

    @classmethod
    def decode(cls, value: Union[str, bytes]) -> "JWT":
        """Decode a JWT as string or bytes into JWT instance"""
        value = value if isinstance(value, bytes) else value.encode("utf-8")
        raw_header, raw_payload, raw_signature = value.split(b".")
        header = Header.parse_raw(urlsafe_b64decode(raw_header + b"=="))
        claims = Claims.parse_raw(urlsafe_b64decode(raw_payload + b"=="))
        decoded_signature = urlsafe_b64decode(raw_signature + b"==")
        return JWT(
            header=header,
            claims=claims,
            signature=decoded_signature,
        )


def create_nkey(
    signing_nkeys: Union[
        str, bytes, Path, io.TextIOBase, io.BufferedIOBase, nkeys.KeyPair, None
    ] = None,
    role: str = "user",
) -> nkeys.KeyPair:
    """Generate a new operator nkey"""
    # Make sure role is valid
    role = Role(role.upper())
    # Generate a new key (use nsc at the moment, maybe we could vendor `nk` binary which is much smaller)
    # Note that "nsc generate nkey" command does not require an environment to be setup.
    cmd = ["nsc", "generate", "nkey", f"--{role.value.lower()}"]
    # Extend command using private key if necessary
    if signing_nkeys:
        keypair = load_keys(signing_nkeys)
        cmd.extend(["--private-key", keypair.seed])
    # Execute command
    result = run(cmd, stderr=PIPE)
    # Return ney key pair (public/private)
    return nkeys.from_seed(result.stderr.splitlines(False)[0])


def create_jwt(
    signing_nkeys: Union[
        str, bytes, Path, io.TextIOBase, io.BufferedIOBase, nkeys.KeyPair, None
    ],
    user_nkeys: Union[
        str, bytes, Path, io.TextIOBase, io.BufferedIOBase, nkeys.KeyPair
    ],
    nats: Optional[NATSAttrs] = None,
    name: Optional[str] = None,
    account_public_key: Union[str, bytes, None] = None,
    _iat: Optional[int] = None,
) -> JWT:
    """Create a new JWT"""
    # Load keys
    signing_keypair = load_keys(signing_nkeys)
    user_keypair = load_keys(user_nkeys)
    # Issued At timestamp in Unix seconds
    iat = int(time.time()) if _iat is None else _iat
    # Issuer is the public key associated with the signing key
    iss = signing_keypair.public_key.decode("utf-8")
    # Subject is the public key associated with the user key
    sub = user_keypair.public_key.decode("utf-8")
    # Generate permissions
    nats = NATSAttrs.parse_obj(nats) if nats else NATSAttrs()
    if account_public_key is not None:
        nats.issuer_account = (
            account_public_key.decode("utf-8")
            if isinstance(account_public_key, bytes)
            else account_public_key
        )
    # Generate claims
    claims = Claims(
        jti="",
        iat=iat,
        iss=iss,
        name=name or sub,
        sub=sub,
        nats=nats,
    )
    # Export claims to JSON
    claims_to_hash = claims.json(exclude_unset=True, by_alias=True).encode("utf-8")
    jti = b32encode(sha256(claims_to_hash).digest()).strip(b"=")
    # Update claims
    claims.jti = jti.decode("utf-8")
    # Encode JWT
    encoded_header = urlsafe_b64encode(Header().json().encode("utf-8")).strip(b"=")
    encoded_body = urlsafe_b64encode(
        claims.json(exclude_unset=True, by_alias=True).encode("utf-8")
    ).strip(b"=")
    # Gather data to sign
    signed = b".".join([encoded_header, encoded_body])
    # Compute signature
    signature = signing_keypair.sign(signed)
    # Return new JWT instance
    return JWT(claims=claims, signature=signature, signed=signed)


def create_creds(
    user_nkeys: Union[
        str, bytes, Path, io.TextIOBase, io.BufferedIOBase, nkeys.KeyPair
    ],
    user_jwt: JWT,
) -> bytes:
    """Create credential file according to JWT and user nkeys"""
    # Wrte jwt as string
    jwt = user_jwt.encode().decode("utf-8")
    seed = load_keys(user_nkeys).seed.decode()
    template = """-----BEGIN NATS USER JWT-----
{jwt}
------END NATS USER JWT------

************************* IMPORTANT *************************
    NKEY Seed printed below can be used to sign and prove identity.
    NKEYs are sensitive and should be treated as secrets.

-----BEGIN USER NKEY SEED-----
{seed}
------END USER NKEY SEED------

*************************************************************"""
    # Generate credentials
    return template.format(jwt=jwt, seed=seed).encode("utf-8")


def create_user(
    signing_nkeys: Union[
        str, bytes, Path, io.TextIOBase, io.BufferedIOBase, nkeys.KeyPair
    ],
    nats: Optional[NATSAttrs] = None,
    name: Optional[str] = None,
    account_public_key: Union[str, bytes, None] = None,
) -> Tuple[JWT, bytes, nkeys.KeyPair]:
    # Load signing keys
    signing_keypair = load_keys(signing_nkeys)
    # New user nkey (nkey seed and public key)
    keys = create_nkey(signing_keypair, role="user")
    # Issuer is the public key associated with the private signing key
    jwt = create_jwt(
        signing_nkeys=signing_keypair,
        user_nkeys=keys,
        nats=nats,
        name=name,
        account_public_key=account_public_key,
    )
    creds = create_creds(user_nkeys=keys, user_jwt=jwt)
    # Return JWT, credentials and nkeys
    return jwt, creds, keys


class User:
    def __init__(self, jwt: JWT, creds: bytes, keys: nkeys.KeyPair) -> None:
        self.jwt = jwt
        self.creds = creds
        self.nkeys = keys

    @property
    def claims(self) -> Claims:
        return self.jwt.claims

    def write_creds(self, output: Union[str, Path]) -> Path:
        output = Path(output)
        output.write_bytes(self.creds)
        return output

    def write_seed(self, output: Union[str, Path]) -> Path:
        output = Path(output)
        output.write_bytes(self.nkeys.seed)
        return output

    def __repr__(self) -> str:
        return f"User(claims={repr(self.jwt.claims)})"


class Issuer:
    def __init__(self, config: Optional[IssuerConfig] = None) -> None:
        self.config = config or IssuerConfig.parse()
        self.keypair = nkeys.from_seed(self.config.account_signing_key.encode())

    @property
    def public_keys(self) -> IssuerPublicKeys:
        return IssuerPublicKeys(
            account_key=self.config.account_public_key or self.keypair.public_key,
            signing_key=self.keypair.public_key,
        )

    def create_user(
        self, name: Optional[str] = None, nats: Optional[NATSAttrs] = None
    ) -> User:
        jwt, creds, keys = create_user(
            self.config.account_signing_key,
            nats=nats,
            name=name,
            account_public_key=self.config.account_public_key,
        )
        return User(jwt, creds, keys)

    @contextmanager
    def temporary_creds(
        self, name: Optional[str], nats: Optional[NATSAttrs] = None
    ) -> Iterator[Path]:
        # Create a new user
        user = self.create_user(name, nats)
        # Create a temporary directory
        with TempDir() as directory:
            # Create credential file path
            creds_file = directory.path / "creds"
            # Write credentials
            user.write_creds(creds_file)
            # Yield user and credentials
            # Note that there is no need to cleanup credentials since directory will be removed
            yield creds_file.resolve(True)
