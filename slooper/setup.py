from setuptools import find_packages, setup

setup(
    name="slooper",
    version="0.1",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "sounddevice",
        "soundfile",
        "numpy",
        "PyYAML",
        "flask",
        "flask-socketio",
        "gevent",
        "gevent-websocket",
        "waitress",
    ],
)
