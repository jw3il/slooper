"""
Extends flask app with websockets to synchronize the state across clients.
"""

from slooper.app import app_flask
import logging
from flask import request
from flask_socketio import SocketIO


socketio = SocketIO(app_flask.app, logger=logging.getLogger(), engineio_logger=True)
socketio_session_ids = []


@socketio.on("connect")
def connect():
    socketio_session_ids.append(request.sid)
    logging.info(f"SocketIO: Connect {request.sid} (total {len(socketio_session_ids)})")


@socketio.on("disconnect")
def disconnect():
    socketio_session_ids.remove(request.sid)
    logging.info(
        f"SocketIO: Disconnect {request.sid} (total {len(socketio_session_ids)})"
    )


def broadcast_to_others(event, data, own_sid):
    for c in socketio_session_ids:
        if c != own_sid:
            socketio.emit(event, data, room=c)


def socketio_change_handler():
    """
    Broadcasts the current state to other socketio_session_ids.
    """
    sid = request.args.get("sid", None)
    if sid is not None and sid != "":
        state_dict = app_flask.get_state_dict("Client {sid} has modified the state")
        broadcast_to_others("update", state_dict, sid)


# update state changed event handler
app_flask.e_changed_state = socketio_change_handler
app_flask.websocket_support = True
