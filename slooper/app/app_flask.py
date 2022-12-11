"""
Main flask webapp.
"""

from contextlib import contextmanager
import logging
from datetime import datetime

from flask import Flask, send_file, abort, jsonify, render_template
import os
from slooper.core.recording import State
import slooper.core.stream as stream
import string
from sys import platform
from threading import Lock


app = Flask(__name__)
websocket_support = False
load_lock = Lock()


def e_changed_state():
    """
    Called when a HTTP request has changed the state, to be reassigned.
    """
    pass


def try_stream_start(cfg):
    try:
        stream.stream_start(device=cfg["device"], latency=cfg["latency"])
        return True
    except ValueError as e:
        logging.error(e)
        return False


def reset_usb(cfg):
    RESET_USB_DEVICES_KEY = "reset-usb-devices"
    assert isinstance(
        cfg[RESET_USB_DEVICES_KEY], list
    ), f"Error: '{RESET_USB_DEVICES_KEY}' has to be a list!"
    for id in cfg[RESET_USB_DEVICES_KEY]:
        reset_usb_device(id)


def load():
    if stream.stream is not None:
        return True

    # only one thread should try loading
    with load_lock:
        logging.info("Loading..")
        cfg = stream.load_config()

        # try to start the stream
        if try_stream_start(cfg):
            return True

        # reset usb devices if loading failed
        reset_usb(cfg)

    return False


def reset_usb_device(id: str):
    """
    Resets the usb device with the given id string.

    :param id: the usb id
    """
    # executing code as sudo with arbitrary arguments is very dangerous
    # => at least check that the string only contains hex digits and ':'
    if all(c in string.hexdigits + ":" for c in id):
        if platform == "linux" or platform == "linux2":
            logging.warning(f"Trying to reset USB device '{id}'")
            os.system(f"sudo usbreset {id}")
        else:
            logging.error(f"USB reset not implemented on platform {platform}")
    else:
        logging.error(f"Invalid usb id '{id}'")


@app.route("/poweroff")
def poweroff():
    if platform == "linux" or platform == "linux2":
        os.system("sudo poweroff")
        return "Poweroff"
    else:
        logging.error(f"Poweroff not implemented on platform {platform}")
        return f"Poweroff not implemented on platform {platform}"


@app.route("/")
def main():
    # make sure stream is loaded / try to load stream
    load()
    # show main page with controls
    return render_template("main.html", websocket=websocket_support)


@app.route("/close")
def close():
    with stream.lock:
        stream.stream_close()
        stream.recordings.clear()
    return "Close"


def get_state_dict(info: str = "", lock_stream=True):
    if lock_stream:
        stream.lock.acquire()

    state_dict = {
        "stream": stream.get_stream_info_dict(),
        "recordings": dict(
            map(
                lambda pair: (pair[0], pair[1].get_info_dict()),
                stream.recordings.items(),
            )
        ),
        "info": info,
    }

    if lock_stream:
        stream.lock.release()

    return state_dict


def get_state_response(info: str = "", lock_stream=True):
    return jsonify(get_state_dict(info, lock_stream))


@app.route("/state")
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


@app.route("/delete/<string:key>")
def delete(key):
    with stream_context():
        delete_recording(key)

    e_changed_state()
    return get_state_response(f"Deleted {key}")


@app.route("/download/<string:key>")
def download(key):
    with stream_context():
        r = get_recording(key)
        bytes_io = r.create_bytes_io(stream.stream.samplerate)
        bytes_io.seek(0)
        time_str = datetime.fromtimestamp(r.timestamp).strftime("%Y_%m_%d-%H_%M")
        return send_file(
            bytes_io,
            "audio/flac",
            as_attachment=True,
            download_name=f"{time_str}-{key}.flac",
        )


@app.route("/record/<string:key>")
def record(key):
    with stream_context():
        get_recording(key, can_create=True).state = State.Record

    e_changed_state()
    return get_state_response(f"Start Recording at {key}")


@app.route("/set-frame/<string:key>/<int:frame>")
def set_frame(key, frame):
    with stream_context():
        r = get_recording(key)
        if r.state == State.Record:
            abort(400, "Cannot set frame while recording")
        r.set_frame(frame)

    e_changed_state()
    return get_state_response(f"Set frame of {key} to {frame}")


@app.route("/set-name/<string:key>/<string:name>")
def set_name(key, name):
    with stream_context():
        get_recording(key).name = name

    e_changed_state()
    return get_state_response(f"Set name of {key} to {name}")


@app.route("/pause/<string:key>")
def pause(key):
    with stream_context():
        get_recording(key).state = State.Pause

    e_changed_state()
    return get_state_response(f"Paused Recording at {key}")


@app.route("/pause")
def pause_all():
    with stream_context():
        for r in stream.recordings.values():
            r.state = State.Pause

    e_changed_state()
    return get_state_response("Paused all recordings")


@app.route("/loop/<string:key>")
def loop(key):
    with stream_context():
        get_recording(key).state = State.Loop

    e_changed_state()
    return get_state_response(f"Started looping of {key}")
