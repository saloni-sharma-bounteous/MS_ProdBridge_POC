#!/usr/bin/env bash
# Apply the migrations with the Flyway command-line tool. Set FLYWAY_URL, FLYWAY_USER and FLYWAY_PASSWORD first.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
flyway -configFiles="$here/flyway.conf" info
flyway -configFiles="$here/flyway.conf" validate
flyway -configFiles="$here/flyway.conf" migrate
flyway -configFiles="$here/flyway.conf" info
