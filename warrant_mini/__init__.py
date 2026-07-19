"""warrant-mini — a miniature AI marketing-compliance checker.

We verify TLS against the operating system's native trust store (via
`truststore`) rather than certifi's bundled roots. On networks that do TLS
inspection (corporate Zscaler proxies and the like), the interception CA lives
in the OS keychain — which the OS verifier accepts but OpenSSL's stricter
bundled verification rejects. Injecting truststore at import time lets both the
Anthropic client and the URL fetcher work behind such proxies with no per-user
configuration.
"""

from __future__ import annotations

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001 — never let trust-store setup break the tool
    pass
