#!/bin/sh
KEY_PATH=".likelines_secret_key"

echo "[KEY] Generating secret key..."

if [ -f "$KEY_PATH" ]; then
    echo "[KEY] Old key found in: $KEY_PATH"
else
    python -m LikeLines.secretkey > $KEY_PATH
    echo "[KEY] Created key in: $KEY_PATH"
fi

echo -n "[KEY] *** " | cat - $KEY_PATH



