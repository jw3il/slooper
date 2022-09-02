import argparse
import logging.config

# setup logging
logging.config.dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(module)s %(levelname)s > %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

# load main app
import app_flask
app = app_flask.app
app_flask.load()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Looper server')
    parser.add_argument('--host', type=str, default="localhost", help="The host to listen on")
    parser.add_argument('--port', type=int, default=5000, help="The port to listen on")
    parser.add_argument('--debug', action='store_true', help="Enable debug mode")
    parser.add_argument('--websocket', action='store_true', help="Enable web socket sync mode")
    args = parser.parse_args()

    if args.websocket:
        # run with socketio
        logging.warning(f"Launching looper with websocket support on http://{args.host}:{args.port}")
        import app_socketio
        app_socketio.socketio.run(app, host=args.host, port=args.port, debug=args.debug)
    else:
        # run app directly
        logging.warning(f"Launching looper on http://{args.host}:{args.port}")
        app.run(host=args.host, port=args.port, debug=args.debug)
