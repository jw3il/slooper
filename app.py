from contextlib import contextmanager
import logging
from datetime import datetime
from webbrowser import get

from flask import Flask, send_file, abort, jsonify
from flask import request
from flask_socketio import SocketIO, emit
import os
from soundlooper.recording import State
import soundlooper.stream as stream


app = Flask(__name__)


def load():
    if stream.stream is not None:
        return True

    logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
    logging.info("Launching..")
    cfg = stream.load_config()

    try:
        # start stream
        stream.stream_start(device=cfg["device"], latency=cfg["latency"], search_timeout=0.1)
        return True
    except ValueError as e:
        logging.error(e)
        return False


@app.route('/')
def main():
    load()
    # show main page with controls
    return app.send_static_file('main.html')


@app.route('/poweroff')
def poweroff():
    os.system('sudo poweroff')
    return "Poweroff"


@app.route('/close')
def close():
    with stream.lock:
        stream.stream_close()
        stream.recordings.clear()
    return "Close"


def get_state_dict(info: str = '', lock_stream=True):
    if lock_stream:
        stream.lock.acquire()

    state_dict = {
        'stream': stream.get_stream_info_dict(),
        'recordings': dict(map(lambda pair: (pair[0], pair[1].get_info_dict()), stream.recordings.items())),
        'info': info
    }

    if lock_stream:
        stream.lock.release()

    return state_dict


def get_state_response(info: str = '', lock_stream=True):
    return jsonify(get_state_dict(info, lock_stream))


@app.route('/state')
def state():
    load()
    return get_state_response()


@contextmanager
def stream_context():
    if stream.stream is None:
        abort(400, "No stream available")
    stream.lock.acquire()
    try:
        yield
    finally:
        stream.lock.release()


def get_recording(key, can_create=False):
    if key in stream.recordings:
        return stream.recordings[key]
    elif can_create:
        return stream.recordings[key]
    else:
        abort(404, f"Recording with key '{key}' does not exist")

def delete_recording(key):
    if key in stream.recordings:
        del stream.recordings[key]
    else:
        abort(404, f"Recording with key '{key}' does not exist")


@app.route('/delete/<string:key>')
def delete(key):
    with stream_context():
        delete_recording(key)
    
    request_has_changed_state()
    return get_state_response(f'Deleted {key}')


@app.route('/download/<string:key>')
def download(key):
    with stream_context():
        r = get_recording(key)
        bytes_io = r.create_bytes_io(stream.stream.samplerate)
        bytes_io.seek(0)
        time_str = datetime.fromtimestamp(r.timestamp).strftime("%Y_%m_%d-%H_%M")
        return send_file(bytes_io, 'audio/flac', as_attachment=True, download_name=f"{time_str}-{key}.flac")


@app.route('/record/<string:key>')
def record(key):
    with stream_context():
        get_recording(key, can_create=True).state = State.Record

    request_has_changed_state()
    return get_state_response(f'Start Recording at {key}')


@app.route('/set-frame/<string:key>/<int:frame>')
def set_frame(key, frame):
    with stream_context():
        r = get_recording(key)
        if r.state == State.Record:
            abort(400, "Cannot set frame while recording")
        r.set_frame(frame)

    request_has_changed_state()
    return get_state_response(f'Set frame of {key} to {frame}')


@app.route('/set-name/<string:key>/<string:name>')
def set_name(key, name):
    with stream_context():
        get_recording(key).name = name

    request_has_changed_state()
    return get_state_response(f'Set name of {key} to {name}')


@app.route('/pause/<string:key>')
def pause(key):
    with stream_context():
        get_recording(key).state = State.Pause

    request_has_changed_state()
    return get_state_response(f'Paused Recording at {key}')


@app.route('/pause')
def pause_all():
    with stream_context():
        for r in stream.recordings.values():
            r.state = State.Pause
    
    request_has_changed_state()
    return get_state_response("Paused all recordings")


@app.route('/loop/<string:key>')
def loop(key):
    with stream_context():
        get_recording(key).state = State.Loop

    request_has_changed_state()
    return get_state_response(f'Started looping of {key}')


# socket.io to sync state between clients
socketio = SocketIO(app)
clients = []

@socketio.on('connect')
def connect():
    clients.append(request.sid)
    logging.info(f"SocketIO: Connect {request.sid} (total {len(clients)})")

@socketio.on('disconnect')
def disconnect():
    clients.remove(request.sid)
    logging.info(f"SocketIO: Disconnect {request.sid} (total {len(clients)})")


def broadcast_to_others(event, data, own_sid):
    for c in clients:
        if c != own_sid:
            socketio.emit(event, data, room=c)


def request_has_changed_state():
    """
    Called when a HTTP request has changed the state. Broadcasts the current state to other clients.
    """
    sid = request.args.get('sid', None)
    if sid is not None and sid != '':
        state_dict = get_state_dict("Client {sid} has modified the state")
        broadcast_to_others('update', state_dict, sid)
