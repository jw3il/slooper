#!/bin/bash

# allow overriding default settings
if [ -z "${HOST}" ]; then
    HOST=0.0.0.0
fi

if [ -z "${PORT}" ]; then
    PORT=8080
fi

USAGE="\
Looper: Web-based looping interface
Usage: $(basename $0) [-h|-w|-d|-i|-a|-z|-u]

General Options:
-h    Print this help message
-p    Start server in production mode (default)
-d    Start server in development mode

Service Options (require sudo & systemd):
-i    Install this script as a service (starts at boot)
-a    Starts the looper service
-l    View looper service log
-z    Stops the looper service
-u    Uninstall the looper service"

REAL_PATH=$(realpath "$0")
SCRIPT_DIR="$(dirname ${REAL_PATH})"

SERVICE="\
[Unit]
Description=Looper Web Server

[Install]
WantedBy=multi-user.target

[Service]
ExecStart=/bin/bash ${REAL_PATH} -p
Type=simple
User=${USER}
Restart=on-failure"

while getopts ":hpdialzu" option; do
   case $option in
      h)
         echo "$USAGE"
         exit 0;;
      p)
         DEVELOPMENT=false;;
      d)
         DEVELOPMENT=true;;
      i)
         echo "Creating looper service.."
         echo "${SERVICE}" > "${SCRIPT_DIR}/looper.service"
         (set -x; sudo systemctl enable "${SCRIPT_DIR}/looper.service")
         exit 0;;
      a)
         (set -x; sudo systemctl start looper.service)
         exit 0;;
      l)
         (set -x; journalctl -f -u looper)
         exit 0;;
      z)
         (set -x; sudo systemctl stop looper.service)
         exit 0;;
      u)
         (set -x; sudo systemctl disable looper.service)
         exit 0;;
      \?) # invalid option
         echo "Error: Invalid option"
         echo ""
         echo "${USAGE}"
         exit 1;;
   esac
done

if [ -z "${DEVELOPMENT}" ]; then
   echo "${USAGE}"
   exit 0
fi

# cd to the directory of this script
cd "${SCRIPT_DIR}"
export PYTHONPATH="${SCRIPT_DIR}"

# set server env variables and run server
if [ "${DEVELOPMENT}" = true ]; then
   export FLASK_ENV=development
   python app.py --host=$HOST --port=$PORT
else
   export FLASK_ENV=production
   python -O app.py --host=$HOST --port=$PORT
fi

# return exit status of server
exit_status="$?"
exit ${exit_status}
