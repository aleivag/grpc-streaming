#!/usr/bin/env python3
import logging
import os
import pty
import select
import time
import tty
import traceback

from concurrent.futures import ThreadPoolExecutor
from shlex import split
from subprocess import Popen
from threading import Thread

import grpc

from config import PORT, SERVER
from proto.cli_pb2 import Line
from proto.cli_pb2_grpc import add_cliServicer_to_server, cliServicer


logger = logging.getLogger("server")
logging.basicConfig(level=logging.DEBUG)

class StdinPipe(Thread):
    def __init__(self, buffer: Line, pipe: int) -> None:
        self.buffer = buffer
        self.pipe = pipe
        super().__init__()

    def run(self):
        for line in self.buffer:
            logging.debug(f"=>{line.buffer.encode()}")
            os.write(self.pipe, line.buffer.encode())


class Server(cliServicer):
    def call(self, lines, context):
        # We read the first line of the message and that's the cmd line to execute, then
        # we start a subprocess and just plugs the process stdin to the streaming request lines
        # and we yield the process stdout back to the client.

        try:
            # read first line as it contains the command to execute
            cmd = split(next(lines).buffer)

            process_master_pty, process_follower_pty = pty.openpty()
            stdin_master_pty, stdin_follower_fd = pty.openpty()

            # setting this one raw, allow us to echo characters back to the client
            tty.setraw(stdin_follower_fd)

            # this thread just takes the lines and iterate over them writitng the content in stdin_master_pty
            # that would be used to write into the application.
            t = StdinPipe(lines, stdin_master_pty)
            t.start()

            with Popen(
                cmd,
                preexec_fn=os.setsid,
                stdin=process_follower_pty,
                stdout=process_follower_pty,
                stderr=process_follower_pty,
                universal_newlines=True,
            ) as p:
                while p.poll() is None:
                    r, w, e = select.select(
                        [stdin_follower_fd, process_master_pty], [], []
                    )
                    if stdin_follower_fd in r:
                        d = os.read(stdin_follower_fd, 10240)
                        os.write(process_master_pty, d)
                    elif process_master_pty in r:
                        readline = os.read(process_master_pty, 10240)
                        logging.debug(f"<={readline}")
                        yield Line(buffer=readline)

        except Exception as e:
            print(f"error at {e}")
            traceback.print_exception(e)
            raise


def serve():
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    add_cliServicer_to_server(Server(), server)
    server.add_insecure_port(f"{SERVER}:{PORT}")
    server.start()
    try:
        while True:
            time.sleep(3_600)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve()
