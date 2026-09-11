#!/bin/sh
set -eu
mkdir -p /data/operacional/data /data/operacional/logs
chown -R operacional:operacional /data/operacional
exec gosu operacional python run.py
