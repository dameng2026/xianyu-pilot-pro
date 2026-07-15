# Supply-chain and commercial release gate

Status: fail-closed. CI verifies source/dependency/container inputs, but the
external registry and provenance trust root are not provisioned. The intentional
`release-provenance-gate` rejects every Git tag until that external work is
implemented and independently reviewed.

## What the tracked CI proves

- full Git-history Gitleaks scan with redacted findings;
- hash-locked Python/release tooling and locked npm/Maven dependency gates;
- tests, builds, migration/release contracts and monitoring config checks;
- CycloneDX **SBOM** output for Java, Python, npm projects and every production
  container subject;
- fail-closed dependency audits and container scans for HIGH/CRITICAL findings,
  including unfixed findings;
- evidence artifacts named with the exact source revision.

This local evidence **does not prove** that a locally built image is the image later run in
production, that a mutable base tag resolves to the same bytes tomorrow, that a
registry account is least privilege, or that a dependency license is approved
for commercial use. A green branch workflow is not a releasable artifact.

GitHub retains the configured CI artifacts for **30 days**. That window supports
debugging; it is not the commercial release archive. Before any release, copy
the evidence into the immutable, access-controlled release record under the
approved retention policy and verify its checksums.

## Registry, signing and provenance acceptance

The isolated release workflow must:

1. Build the five application images from a protected, reviewed Git revision in
   one controlled workflow. Never promote an operator workstation image.
2. Push to an approved immutable registry using short-lived GitHub OIDC and a
   repository-scoped least-privilege identity. Pull requests and ordinary CI
   jobs get neither `packages: write` nor `id-token: write`.
3. Resolve every deployed subject as `repository@sha256:...`; mutable tags may
   be human aliases but are never deployment or verification authority.
4. Create a keyless signature with an exact certificate issuer and workflow
   identity, an in-toto/**SLSA** provenance statement bound to the digest, and
   a digest-bound SBOM/scan record.
5. Verify the signature, identity, issuer, provenance subject/materials and
   policy before deployment. Wildcard identities, self-asserted JSON, tag-only
   checks and screenshots fail the gate.
6. Retain the approved image digests so rollback does not rebuild old source
   against changed registries/base images. Test pull, deploy and rollback from
   the disaster-recovery environment.

Only after the external registry/OIDC policy exists may a reviewed change
replace the current failing tag job. The replacement must fail closed when any
image, signature, SBOM, scan or attestation is absent or digest-mismatched.

## Dependency and license review

Security scanning and **license** approval are separate decisions. For every
release, legal/compliance reviews the complete SBOM, direct/transitive licenses,
notices, source-offer/redistribution obligations, commercial restrictions and
runtime/container packages. Record approval or a time-bound, named exception;
do not infer approval from an SPDX string or “open source” label. Hibernate's
LGPL-2.1-only obligations remain an explicit production-readiness gate.

Renovation/upgrades use a reviewed pull request with changelog, compatibility,
test, vulnerability, license and rollback evidence. Scanner, GitHub Action,
base-image and infrastructure-image changes receive the same review as
application code. All Actions remain commit-SHA pinned; downloaded executables
must be version/checksum pinned and never installed with `curl | sh`.

## Required release evidence pack

- protected Git commit and successful CI run URL;
- secret-scan, test, migration and monitoring-config results;
- source and image SBOMs, vulnerability reports and accepted exceptions;
- immutable application/infrastructure image digests;
- signature and SLSA/in-toto verification output with exact identity/issuer;
- license/legal approval and third-party notices;
- migration, backup/restore, DAST/penetration, capacity and operational drill
  evidence required by `../production-readiness.md`;
- release ID, operator/approver, change ticket, deployment timestamps and final
  public smoke/rollback result.

A generated JSON file, local digest, branch scan or operator attestation does
not prove the external artifact exists or is trustworthy. Missing independent
registry, backup, legal or operational evidence keeps the release blocked.
