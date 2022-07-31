#!/bin/bash

# allow overriding default settings
if [ -z "${IP}" ]; then
    IP=0.0.0.0
fi

if [ -z "${PORT}" ]; then
    PORT=8080
fi

USAGE="\
Looper: Web-based looping interface
Usage: $(basename $0) [-h|-w|-d|-i|-a|-z|-u]

General Options:
-h    Print this help message
-w    Start server in production mode (waitress)
-d    Start server in debug mode (flask debug mode)

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
ExecStart=/bin/bash ${REAL_PATH} -w
Type=simple
User=${USER}
Restart=on-failure"

while getopts ":hwdialzu" option; do
   case $option in
      h)
         echo "$USAGE"
         exit 0;;
      w)
         DEBUG=false;;
      d)
         DEBUG=true;;
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

if [ -z "${DEBUG}" ]; then
   echo "${USAGE}"
   exit 0
fi

# cd to the directory of this script
pushd "${SCRIPT_DIR}"

# add local bin path
PATH=$PATH:/home/$USER/.local/bin

# run the server
if [ "${DEBUG}" = true ]; then
    # debug mode with flask
    FLASK_APP=main
    FLASK_ENV=development
    flask run --host=$IP --port=$PORT
else
    # production mode with waitress
    waitress-serve --listen $IP:$PORT main:app
fi
return_code="$?"

# switch back directory and exit
popd
exit ${return_code}
