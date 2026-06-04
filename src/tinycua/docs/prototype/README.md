# Prototype Documentation

This directory contains prototype-level documentation for the TINYCUA project.

## Purpose

The `docs/prototype/` directory serves as a lightweight documentation scaffold for early-stage design decisions, architectural notes, and experimental ideas that do not yet warrant formal spec/design documents.

## Structure

```
docs/prototype/
├── README.md          # This file — explains the directory purpose
├── <topic>.md         # Ad-hoc prototype docs (added as needed)
└── ...
```

## Guidelines

- **Keep it lightweight**: Prototype docs are informal and may be incomplete.
- **Link to specs**: When a prototype doc matures into a formal decision, reference the corresponding `specs/` document.
- **Archive when done**: Once a feature moves past prototype stage, move relevant content to `specs/` and remove the prototype doc.

## Related

- Formal specifications: `../../specs/`
- Design documents: `../../specs/<feature>/design.md`
