# sdk-generation

This repository drives ImageKit SDK generation via [Stainless](https://stainlessapi.com/).

## Branches

| Branch | Purpose |
|--------|---------|
| `main` | OpenAPI spec and Stainless config targeting all SDKs **except C#** |
| `csharp` | OpenAPI spec and Stainless config targeting the **C# SDK only** |

The C# target is maintained on a separate branch because it requires certain changs to resolve build warnings that were introducing breaking changes in Go and Java SDKs. This diversion can merge once Go and Java SDKs are releasing a major version update.
