# Validation Report

Validated for the public-repository packet.

## Checks completed

- Parsed all generated YAML registries.
- Verified 14 unique one-PR work-packet IDs.
- Verified all dependencies reference known packets.
- Verified the execution graph is acyclic.
- Verified CSV issue rows match the YAML packet registry.
- Verified every packet file named by the CSV exists.
- Compiled all reference Python templates and the packet validator.
- Generated SHA-256 manifest and checksum inventory.
- Removed raw source/conversation transcripts from the public packet while retaining the derived decisions in the implementation documents.

## Repository limitation

The packet records the repository facts obtained through the connected GitHub integration. It does not claim that the exact release commit was rebuilt inside the artifact-generation environment; A1-000 explicitly requires fresh exact-main CI/build evidence.

## Counts

```text
work packets: 14
milestones reconciled: 16
```
