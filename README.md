# 🔁 Looper

*Looper* is a web-based audio recording and playback tool tailored for looping.
Its main purpose is to add looping functionality to guitar amps with USB audio interfaces.

Connect it to your amp with a Raspberry Pi, your Laptop or PC and control the looper from any device in your network.
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
- [ ] Consistent over multiple devices
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

These python packages have additional requirements that may or may not be installed on your system. 
On a fresh installation of `Raspbian GNU/Linux 11 (bullseye)`, you have to install `libatlas-base-dev` for `numpy` and `libportaudio2` and `libsndfile1-dev` for `sounddevice`:

```
$ sudo apt install libatlas-base-dev libportaudio2 libsndfile1-dev
```

Congratulations, you are done!

## System Configuration

### Poweroff (Linux only)

Looper has a button to power off your system. This button simpy calls `sudo poweroff` on the server. To make this work
without user interaction, you can edit `/etc/sudoers` with `visudo` and allow your user `user_name` to poweroff the
system (and more):

```
user_name ALL=(ALL) NOPASSWD: /sbin/poweroff, /sbin/reboot, /sbin/shutdown
```

## Running Looper

Looper comes with tiny helper scripts to run it in different modes

### Production Mode

Execute `looper.sh -p` to run the app in production mode with [gevent](http://www.gevent.org/).
We recommend to use this mode for playing with looper, as the UI latency will usually be much lower than in development mode. 

###  Development Mode

Execute `looper.sh -d` to run the app in development mode with the built-in flask development server.
Note that this webserver is quite slow, only use this option for development.

## Contributing

You found a bug or have an idea?
Contributions are welcome, just open a new issue or create a pull request.
