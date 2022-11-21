import os
import selectors
import sys
import tty

import grpc

from config import PORT, SERVER
from proto.cli_pb2 import Line
from proto.cli_pb2_grpc import cliStub


def redirect(stdin_fd, stdout_fd):
    sel = selectors.DefaultSelector()
    sel.register(stdin_fd, selectors.EVENT_READ)
    sel.register(stdout_fd, selectors.EVENT_READ)

    # let's send the shell command
    yield Line(buffer="/bin/bash")

    while True:
        events = sel.select(timeout=3)
        for key, mask in events:
            if key.fileobj == stdin_fd:
                line = os.read(key.fileobj, 1024)
                yield Line(buffer=line)
            elif key.fileobj == stdout_fd:
                data = os.read(key.fileobj, 1024)
                os.write(sys.stdout.fileno(), data)
                sys.stdout.flush()


def call():
    channel = grpc.insecure_channel(f"{SERVER}:{PORT}")
    stub = cliStub(channel)
    (pipe_r, pipe_w) = os.pipe()
    stdin = sys.stdin.fileno()
    try:
        stdin_attrs = tty.tcgetattr(stdin)
        tty.setraw(stdin)

        request = redirect(stdin, pipe_r)
        response = stub.call(request)

        for line in response:
            os.write(pipe_w, line.buffer.encode())
    finally:
        tty.tcsetattr(stdin, tty.TCSAFLUSH, stdin_attrs)


if __name__ == "__main__":
    call()
