#!/bin/sh
set -eu

cd /app

LOCKFILE="package-lock.json"
NODE_MODULES_DIR="node_modules"
LOCK_HASH_FILE="${NODE_MODULES_DIR}/.package-lock.sha256"

current_lock_hash="$(node -e "const crypto = require('crypto'); const fs = require('fs'); process.stdout.write(crypto.createHash('sha256').update(fs.readFileSync(process.argv[1])).digest('hex'))" "$LOCKFILE")"

install_reason=""

if [ ! -f "${NODE_MODULES_DIR}/vite/package.json" ]; then
  install_reason="node_modules is empty or incomplete"
elif [ ! -f "$LOCK_HASH_FILE" ]; then
  install_reason="package-lock hash is missing"
elif [ "$(cat "$LOCK_HASH_FILE")" != "$current_lock_hash" ]; then
  install_reason="package-lock.json changed"
fi

if [ -n "$install_reason" ]; then
  echo "Installing frontend dependencies (${install_reason})..."
  npm ci
  printf '%s\n' "$current_lock_hash" > "$LOCK_HASH_FILE"
else
  echo "Reusing existing frontend dependencies."
fi

exec npm run dev -- --host 0.0.0.0 --port 5173
