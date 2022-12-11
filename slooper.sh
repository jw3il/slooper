#!/bin/bash

REAL_PATH=$(realpath "$0")
SCRIPT_DIR="$(dirname ${REAL_PATH})"

# load environment variables
set -a
source "${SCRIPT_DIR}/.env"
set +a

USAGE="\
Slooper: Web-based sound looping interface
Usage: $(basename $0) (-p|-d) [-w|-h|-i|-a|-l|-z|-u]

General Options:
-p    Start server in production mode
-d    Start server in development mode
-w    Adds websocket support to sync states (experimental)
-h    Print this help message

Service Options (require sudo & systemd):
-i    Install this script as a service in production mode (enable websockets with -wi)
-a    Starts the looper service
-l    View looper service log
-z    Stops the looper service
-u    Uninstall the looper service"

assert_dev_undefined() {
   if [ ! -z "${DEVELOPMENT}" ]; then
      echo "Error: Cannot set development and production mode simultaniously 1"
      echo ""
      echo "${USAGE}"
      exit 1
   fi
}

# first check if websockets should be used
WEBSOCKETS=false
unset OPTIND
while getopts ":w" option; do
   case $option in
      w)
         WEBSOCKETS=true;;
      \?)
         ;;
   esac
done

if [ "${WEBSOCKETS}" = true ]; then
   WEBSOCKETS_SERVICE_ARG="-w"
   WEBSOCKETS_ARG="--websocket"
else
   WEBSOCKETS_SERVICE_ARG=""
   WEBSOCKETS_ARG=""
fi

SERVICE="\
[Unit]
Description=Slooper Web Server Service

[Install]
WantedBy=multi-user.target

[Service]
ExecStart=/bin/bash ${REAL_PATH} -p ${WEBSOCKETS_SERVICE_ARG}
Type=simple
User=${USER}
Restart=on-failure"

# then do normal options handling
unset OPTIND
while getopts ":hpdwialzu" option; do
   case $option in
      h)
         echo "$USAGE"
         exit 0;;
      p)
         assert_dev_undefined
         DEVELOPMENT=false;;
      d)
         assert_dev_undefined
         DEVELOPMENT=true;;
      w)
         # do nothing
         ;;
      i)
         echo "Creating slooper service.."
         mkdir -p "${SCRIPT_DIR}/service"
         echo "${SERVICE}" > "${SCRIPT_DIR}/service/slooper.service"
         (set -x; sudo systemctl enable "${SCRIPT_DIR}/service/slooper.service")
         exit 0;;
      a)
         (set -x; sudo systemctl start slooper.service)
         exit 0;;
      l)
         (set -x; journalctl -f -u slooper)
         exit 0;;
      z)
         (set -x; sudo systemctl stop slooper.service)
         exit 0;;
      u)
         (set -x; sudo systemctl disable slooper.service)
         exit 0;;
      \?) # invalid option
         echo "Error: Invalid option"
         echo ""
         echo "${USAGE}"
         exit 1;;
   esac
done

if [ -z "${DEVELOPMENT}" ]; then
   echo "Error: missing argument, you have to select production (-p) or debug (-d) mode."
   echo ""
   echo "${USAGE}"
   exit 1
fi

# cd to the directory of this script
cd "${SCRIPT_DIR}"

# set server env variables and run server
if [ "${DEVELOPMENT}" = true ]; then
   python -m slooper.app --host=$HOST --port=$PORT --debug $WEBSOCKETS_ARG
else
   if [ "${WEBSOCKETS}" = true ]; then
      python -O -m slooper.app --host=$HOST --port=$PORT $WEBSOCKETS_ARG
   else
      python -O -c "from waitress.runner import run; run()" --listen $HOST:$PORT slooper.app.__main__:app
   fi
fi

# return exit status of server
exit_status="$?"
exit ${exit_status}
