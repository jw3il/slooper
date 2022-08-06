import imp
import json
import logging
from datetime import datetime

from flask import Flask, send_file
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


@app.route('/status')
def status():
    load()
    with stream.lock:
        return json.dumps({
            'stream': stream.get_stream_info_dict(),
            'recordings': dict(map(lambda pair: (pair[0], pair[1].get_info_dict()), stream.recordings.items()))
        })


@app.route('/delete/<string:key>')
def delete(key):
    if stream.stream is None:
        return "No stream."

    with stream.lock:
        if key in stream.recordings:
            del stream.recordings[key]
            return f'Deleted {key}'

    return f"{key} does not exist"


@app.route('/download/<string:key>')
def download(key):
    if stream.stream is None:
        return "No stream."

    if key in stream.recordings:
        # might lag as we block the callback while generating the file..
        with stream.lock:
            bytes_io = stream.recordings[key].create_bytes_io(stream.stream.samplerate)
            timestamp = stream.recordings[key].timestamp

        bytes_io.seek(0)
        time_str = datetime.fromtimestamp(timestamp).strftime("%Y_%m_%d-%H_%M")
        return send_file(bytes_io, 'audio/flac', as_attachment=True, download_name=f"{time_str}-{key}.flac")

    return f"{key} does not exist"


@app.route('/record/<string:key>')
def record(key):
    if stream.stream is None:
        return "No stream."

    with stream.lock:
        stream.recordings[key].state = State.Record

    return f'Start Recording at {key}'


@app.route('/set-frame/<string:key>/<int:frame>')
def set_frame(key, frame):
    if stream.stream is None:
        return "No stream."

    with stream.lock:
        if key in stream.recordings:
            stream.recordings[key].set_frame(frame)
    
    return f'Set frame of {key} to {frame}'


@app.route('/set-name/<string:key>/<string:name>')
def set_name(key, name):
    with stream.lock:
        stream.recordings[key].name = name

    return f'Set name of {key} to {name}'


@app.route('/pause/<string:key>')
def pause(key):
    if stream.stream is None:
        return "No stream."

    with stream.lock:
        stream.recordings[key].state = State.Pause

    return f'Paused Recording at {key}'


@app.route('/pause')
def pause_all():
    with stream.lock:
        for r in stream.recordings.values():
            r.state = State.Pause
    
    return "Pause"


@app.route('/loop/<string:key>')
def loop(key):
    if stream.stream is None:
        return "No stream."

    with stream.lock:
        stream.recordings[key].state = State.Loop

    return f'Started Looping at {key}'
