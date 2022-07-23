import json
import logging
import yaml
from yaml import Loader

from flask import Flask, render_template, send_file
import recording
import os

app = Flask(__name__)


@app.before_first_request
def initialize():
    logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
    logging.info("Launching..")

    with open("config.yml", "r") as f:
        cfg = yaml.load(f, Loader=Loader)

    # automatically start stream
    recording.stream_start(device=cfg["device"], latency=cfg["latency"])


@app.route('/')
def main():
    # show main page with controls
    return render_template('main.html')


@app.route('/settings')
def settings():
    # show main page with controls
    return render_template('settings.html', devices=recording.get_devices_list())


@app.route('/poweroff')
def poweroff():
    os.system('poweroff')
    return "Poweroff"


@app.route('/close')
def close():
    recording.stream_close()
    recording.recordings.clear()
    return "Close"


@app.route('/status')
def status():
    global key_counter
    return json.dumps({
        'stream': recording.get_stream_info_dict(),
        'recordings': dict(map(lambda pair: (pair[0], pair[1].get_info_dict()), recording.recordings.items()))
    })


@app.route('/delete/<string:key>')
def delete(key):
    if recording.stream is None:
        return "No stream."

    if key in recording.recordings:
        del recording.recordings[key]
        return f'Deleted {key}'

    return f"{key} does not exist"


@app.route('/download/<string:key>')
def download(key):
    if recording.stream is None:
        return "No stream."

    if key in recording.recordings:
        bytes_io = recording.recordings[key].create_bytes_io()
        bytes_io.seek(0)
        return send_file(bytes_io, 'audio/flac', as_attachment=True, download_name=f"{key}.flac")

    return f"{key} does not exist"


@app.route('/record/<string:key>')
def record(key):
    if recording.stream is None:
        return "No stream."

    recording.recordings[key].state = recording.State.Record
    return f'Start Recording at {key}'


@app.route('/set-frame/<string:key>/<int:frame>')
def set_frame(key, frame):
    if recording.stream is None:
        return "No stream."

    if key in recording.recordings:
        recording.recordings[key].set_frame(frame)
    
    return f'Set frame of {key} to {frame}'


@app.route('/set-name/<string:key>/<string:name>')
def set_name(key, name):
    recording.recordings[key].name = name
    return f'Set name of {key} to {name}'


@app.route('/pause/<string:key>')
def pause(key):
    if recording.stream is None:
        return "No stream."

    recording.recordings[key].state = recording.State.Pause
    return f'Paused Recording at {key}'


@app.route('/pause')
def pause_all():
    for k, r in recording.recordings.items():
        r.state = recording.State.Pause
    
    return "Pause"


@app.route('/loop/<string:key>')
def loop(key):
    if recording.stream is None:
        return "No stream."

    recording.recordings[key].state = recording.State.Loop
    return f'Started Looping at {key}'
