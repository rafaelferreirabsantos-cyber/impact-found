#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt
python3 -m src.run
printf '\nAbra output/dashboard_com_resultados.html\n'
