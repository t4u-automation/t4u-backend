#!/usr/bin/env python3
"""
websockify token plugin for Firebase JWT validation
Validates Firebase JWT token and user_id using public keys (no credentials needed)

Usage: websockify --token-plugin=validate_firebase_jwt.TokenPlugin ...
"""

import json
import os
import sys
import time
from urllib.parse import urlparse, parse_qs, unquote

# Ensure stderr is unbuffered for immediate logging
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True)
else:
    # Fallback for older Python versions
    os.environ['PYTHONUNBUFFERED'] = '1'

try:
    import jwt
    import requests
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    from cryptography import x509
except ImportError:
    print("ERROR: Required packages not installed: pyjwt, requests, cryptography", file=sys.stderr)
    sys.exit(1)

def get_firebase_project_id():
    """Get Firebase project ID from environment variable or metadata file"""
    # 1. Try environment variable first (set when websockify starts)
    project_id = os.getenv("FIREBASE_PROJECT_ID")
    if project_id:
        return project_id
    
    # 2. Try to read from metadata file (written by api_server)
    metadata_path = "/home/user/.vnc_sessions.json"
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
            project_id = metadata.get("firebase_project_id")
            if project_id:
                return project_id
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass
    
    # 3. Fail explicitly if not configured
    error_msg = (
        "ERROR: Firebase project_id not configured. Please set:\n"
        "  1. FIREBASE_PROJECT_ID environment variable, OR\n"
        "  2. Ensure api_server writes firebase_project_id to /home/user/.vnc_sessions.json"
    )
    print(error_msg, file=sys.stderr)
    raise ValueError("Firebase project_id not configured")

# Firebase project ID - read dynamically
FIREBASE_PROJECT_ID = None  # Will be set on first use
FIREBASE_PUBLIC_KEY_URL = f"https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"

# Cache for public keys (refreshed every hour)
_public_keys_cache = {}
_public_keys_expiry = 0

def get_firebase_public_keys():
    """Fetch Firebase public keys from Google"""
    global _public_keys_cache, _public_keys_expiry
    
    # Use cached keys if still valid
    if time.time() < _public_keys_expiry:
        return _public_keys_cache
    
    try:
        response = requests.get(FIREBASE_PUBLIC_KEY_URL, timeout=10)
        response.raise_for_status()
        _public_keys_cache = response.json()
        # Cache for 1 hour (Firebase keys rotate occasionally)
        _public_keys_expiry = time.time() + 3600
        print("INFO: Fetched Firebase public keys", file=sys.stderr)
        return _public_keys_cache
    except Exception as e:
        print(f"ERROR: Failed to fetch public keys: {e}", file=sys.stderr)
        # Return cached keys even if expired as fallback
        return _public_keys_cache if _public_keys_cache else None

def verify_firebase_token(token, retry_refresh=True):
    """Verify Firebase JWT token using public keys"""
    global _public_keys_expiry  # Declare at function start
    
    try:
        # Decode token header to get key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get('kid')
        
        if not kid:
            print("ERROR: Token missing 'kid' in header", file=sys.stderr)
            return None
        
        # Get public keys
        public_keys = get_firebase_public_keys()
        if not public_keys:
            print("ERROR: Could not fetch public keys", file=sys.stderr)
            return None
        
        # Get the specific key for this token
        public_key_pem = public_keys.get(kid)
        if not public_key_pem:
            if retry_refresh:
                # Key not found - Firebase may have rotated keys
                # Force refresh cache and try again
                print(f"WARNING: Public key not found for kid={kid}, refreshing keys...", file=sys.stderr)
                _public_keys_expiry = 0  # Force cache expiry
                public_keys = get_firebase_public_keys()
                public_key_pem = public_keys.get(kid) if public_keys else None
                
                if public_key_pem:
                    print(f"INFO: Found key after refresh for kid={kid}", file=sys.stderr)
                else:
                    print(f"ERROR: Public key still not found for kid={kid} after refresh", file=sys.stderr)
                    return None
            else:
                print(f"ERROR: Public key not found for kid={kid}", file=sys.stderr)
                return None
        
        # Load public key from X.509 certificate
        # Firebase returns certificates, not raw public keys
        try:
            # Try as certificate first
            certificate = x509.load_pem_x509_certificate(
                public_key_pem.encode('utf-8'),
                backend=default_backend()
            )
            public_key = certificate.public_key()
        except Exception:
            # If not a certificate, try as raw public key
            try:
                public_key = serialization.load_pem_public_key(
                    public_key_pem.encode('utf-8'),
                    backend=default_backend()
                )
            except Exception as e:
                print(f"ERROR: Failed to load public key: {e}", file=sys.stderr)
                return None
        
        # Verify token
        # Get project ID dynamically (may change between calls)
        project_id = get_firebase_project_id()
        decoded_token = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            audience=project_id,
            issuer=f"https://securetoken.google.com/{project_id}"
        )
        
        return decoded_token
        
    except jwt.ExpiredSignatureError:
        print("ERROR: JWT token expired", file=sys.stderr)
        return None
    except jwt.InvalidSignatureError as e:
        if retry_refresh:
            # Invalid signature could mean Firebase rotated keys mid-session
            print(f"WARNING: Invalid signature, attempting key refresh: {e}", file=sys.stderr)
            _public_keys_expiry = 0  # Force cache expiry
            # Retry once with refreshed keys
            return verify_firebase_token(token, retry_refresh=False)
        else:
            print(f"ERROR: Invalid JWT signature (after key refresh): {e}", file=sys.stderr)
            return None
    except jwt.InvalidTokenError as e:
        print(f"ERROR: Invalid JWT token: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERROR: Token verification failed: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return None

def load_session_metadata():
    """Load session metadata from file (optional - for ownership check)"""
    metadata_path = "/home/user/.vnc_sessions.json"
    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Metadata file not required - RUN contexts may not have it
        return None
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid session metadata JSON: {e}", file=sys.stderr)
        return None

class TokenPlugin:
    """
    websockify token plugin class for Firebase JWT validation
    websockify will instantiate this class and call lookup() method
    """
    
    def __init__(self, token_source=None):
        """
        Initialize the plugin
        
        Args:
            token_source: Optional source parameter (not used in our case)
        """
        print("INFO: TokenPlugin initialized", file=sys.stderr)
        # Don't initialize Firebase here - wait until first lookup() call
        # This prevents blocking websockify startup if Firebase has network issues
        # Firebase will be initialized lazily on first token validation
    
    def lookup(self, token):
        """
        websockify token plugin interface
        
        Args:
            token: Firebase JWT token from URL query param (?token=...)
                  websockify extracts this from the query string automatically
        
        Returns:
            target (host:port) as tuple if authorized, None if denied
        """
        try:
            # Log token received (for debugging)
            print(f"INFO: lookup called with token length={len(token) if token else 0}", file=sys.stderr)
            
            # Check if token is provided
            if not token:
                print("ERROR: No token provided in request", file=sys.stderr)
                return None
            
            # Validate Firebase JWT token using public keys
            decoded_token = verify_firebase_token(token)
            if decoded_token is None:
                return None
            
            print(f"INFO: JWT token validated successfully", file=sys.stderr)
            
            # Extract user_id for logging purposes
            token_user_id = decoded_token.get('user_id') or decoded_token.get('sub')
            
            # Extract tenant_id from token (custom claim) - OPTIONAL
            # NOTE: Standard Firebase JWT tokens don't include tenant_id
            # It must be set as a custom claim using Firebase Admin SDK
            token_tenant_id = decoded_token.get('tenant_id')
            
            # Load session metadata (optional)
            session_data = load_session_metadata()
            
            # Validate tenant_id ONLY if present in both token AND session
            if session_data:
                session_tenant_id = session_data.get('tenant_id')
                
                # If both have tenant_id, they must match
                if token_tenant_id and session_tenant_id:
                    if token_tenant_id != session_tenant_id:
                        print(f"ERROR: tenant_id mismatch. Token: {token_tenant_id}, Session: {session_tenant_id}", file=sys.stderr)
                        return None
                    print(f"INFO: Authorized - tenant_id verified: {token_tenant_id}", file=sys.stderr)
                else:
                    # No tenant_id validation - allow connection
                    print(f"INFO: Authorized - user_id: {token_user_id} (no tenant_id validation)", file=sys.stderr)
            else:
                # No metadata file - allow connection (e.g., RUN context)
                print(f"INFO: Authorized - user_id: {token_user_id} (no metadata)", file=sys.stderr)
            
            # All checks passed - allow connection
            # Return target as tuple (host, port) - websockify expects this format
            target_host = "localhost"
            target_port = "5900"
            print(f"INFO: Returning target: {target_host}:{target_port}", file=sys.stderr)
            return (target_host, target_port)
            
        except Exception as e:
            print(f"ERROR: Unexpected error in lookup: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return None

