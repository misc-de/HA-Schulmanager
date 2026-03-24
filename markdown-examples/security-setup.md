Set the same secret in both places:

1. Add-on `Schulmanager Bridge`
   - Configuration
   - `bridge_secret: YOUR_SHARED_SECRET`

2. Integration `Schulmanager`
   - Options
   - `Bridge secret: YOUR_SHARED_SECRET`

Then restart the add-on and reload the integration.

Verification:
- `GET /` and `/diagnostics` show `secret_enabled: true`
- requests without the header are rejected with `401`
