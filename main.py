import json
import logging
from datetime import datetime

import yaml
from yaml import Loader

from flask import Flask, render_template, send_file
import recording
import os

app = Flask(__name__)


def load():
    if recording.stream is not None:
        return True

    with open("config.yml", "r") as f:
        cfg = yaml.load(f, Loader=Loader)

    try:
        # start stream
        recording.stream_start(device=cfg["device"], latency=cfg["latency"], search_timeout=0.1)
        return True
    except ValueError as e:
        logging.error(e)
        return False


@app.before_first_request
def initialize():
    logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
    logging.info("Launching..")


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
    with recording.callback_lock:
        recording.stream_close()
        recording.recordings.clear()
    return "Close"


@app.route('/status')
def status():
    load()
    with recording.callback_lock:
        return json.dumps({
            'stream': recording.get_stream_info_dict(),
            'recordings': dict(map(lambda pair: (pair[0], pair[1].get_info_dict()), recording.recordings.items()))
        })


@app.route('/delete/<string:key>')
def delete(key):
    if recording.stream is None:
        return "No stream."

    with recording.callback_lock:
        if key in recording.recordings:
            del recording.recordings[key]
            return f'Deleted {key}'

    return f"{key} does not exist"


@app.route('/download/<string:key>')
def download(key):
    if recording.stream is None:
        return "No stream."

    if key in recording.recordings:
        # might lag as we block the callback while generating the file..
        with recording.callback_lock:
            bytes_io = recording.recordings[key].create_bytes_io()
            timestamp = recording.recordings[key].timestamp

        bytes_io.seek(0)
        time_str = datetime.fromtimestamp(timestamp).strftime("%Y_%m_%d-%H_%M")
        return send_file(bytes_io, 'audio/flac', as_attachment=True, download_name=f"{time_str}-{key}.flac")

    return f"{key} does not exist"


@app.route('/record/<string:key>')
def record(key):
    if recording.stream is None:
        return "No stream."

    with recording.callback_lock:
        recording.recordings[key].state = recording.State.Record

    return f'Start Recording at {key}'


@app.route('/set-frame/<string:key>/<int:frame>')
def set_frame(key, frame):
    if recording.stream is None:
        return "No stream."

    with recording.callback_lock:
        if key in recording.recordings:
            recording.recordings[key].set_frame(frame)
    
    return f'Set frame of {key} to {frame}'


@app.route('/set-name/<string:key>/<string:name>')
def set_name(key, name):
    with recording.callback_lock:
        recording.recordings[key].name = name

    return f'Set name of {key} to {name}'


@app.route('/pause/<string:key>')
def pause(key):
    if recording.stream is None:
        return "No stream."

    with recording.callback_lock:
        recording.recordings[key].state = recording.State.Pause

    return f'Paused Recording at {key}'


@app.route('/pause')
def pause_all():
    with recording.callback_lock:
        for k, r in recording.recordings.items():
            r.state = recording.State.Pause
    
    return "Pause"


@app.route('/loop/<string:key>')
def loop(key):
    if recording.stream is None:
        return "No stream."

    with recording.callback_lock:
        recording.recordings[key].state = recording.State.Loop

    return f'Started Looping at {key}'
