# SARIF Schema

The official SARIF 2.1.0 schema should be placed here for validation.

## Schema URL

The official schema is available at:
- https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-schema-2.1.0.json

## Alternative: Use jsonschema validation

For now, we'll implement basic structural validation instead of full schema validation.
Later we can add the full JSON schema validation once we resolve the download issue.

## Manual Download

If automatic download fails, manually download from:
```bash
wget https://raw.githubusercontent.com/microsoft/sarif-sdk/main/src/Sarif/Schemata/sarif-schema-2.1.0.json \
  -O sarif-schema-2.1.0.json
```
