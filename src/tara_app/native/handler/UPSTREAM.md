# Upstream source

- Repository: https://github.com/deathkernel/TARA-Handler
- Source revision: 617d3bbf10a0bd37dbc69604c405840b9bdb1a4b
- Upstream version: 0.9.0

This directory vendors the C++ headers and implementation sources needed to build the Handler CLI. Upstream test files, workflow files, and project README are not copied. TARA-App's copy changes the `doctor` path to avoid writing a persistent Handler history entry. TARA-App only invokes the fixed `doctor` command; other Handler CLI commands remain outside the app integration.
