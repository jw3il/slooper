# 🔁 Looper

*Looper* is web-based audio recording and playback tool tailored for looping.
Its main purpose is to add looping functionality to guitar amps with USB audio interfaces.

Connect it to your amp with a Raspberry PI, your Laptop or PC and control the looper from any device in your network.
The audio is recorded locally, the recording delay can be adapted according to your device's hardware.
As looper uses the USB audio interface, nothing stops you from simultaneous playback and recording.
Compared to microphone-based solutions, all recordings come straight from your amp without any additional noise.

![](doc/screenshot.png)

## Features

- [x] Local audio recording
- [x] Web-based interface
- [x] Simultaneous playback of multiple recordings
- [x] Record during playback
- [x] Download recordings
- [ ] Control volume per recording
- [ ] Fast loop transition to avoid audio popping
- [ ] Trim recordings
- [ ] Minimalistic UI

## Supported Devices

In theory, looper supports all audio devices that are visible to your operating system.

Looper has been tested with the following audio devices & systems:

| Audio Device                   | Hardware               | Comments | 
|--------------------------------|------------------------|----------|
| Positive Grid Spark Guitar Amp | Raspberry Pi 1 Model B | TODO     |

## Installation

Looper is based on Python 3.10. You can use your system's Python installation or create a virtual environment (e.g. via miniconda):

```
$ conda create -n looper python=3.10
$ conda activate looper
(looper) $
```

Next, clone the repository and set it as your working directory.

```
(looper) $ git clone git@github.com:jw3il/looper.git
(looper) $ cd looper
```

All dependencies can then be installed with `pip`:

```
(looper) $ pip install -r requirements.txt
```

Congratulations, you are done!

## Running Looper

Looper comes with tiny helper scripts to run it in different modes

### Production Mode

Execute `run_waitress.sh` to run the app in production mode with [waitress](https://docs.pylonsproject.org/projects/waitress/en/latest/).
We recommend to use this mode for playing with looper, as the UI latency will usually be much lower than in development mode. 

###  Development Mode

Execute `run_flask.sh` to run the app in development mode with the built-in flask development server.
Note that this webserver is quite slow, only use this option for development.

## Contributing

You found a bug or have an idea?
Contributions are welcome, just open a new issue or create a pull request.
