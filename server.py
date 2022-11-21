import os
import pty
import select
import time
import tty
from concurrent.futures import ThreadPoolExecutor
from shlex import split
from subprocess import Popen
from threading import Thread

import grpc

from config import PORT, SERVER
from proto.cli_pb2 import Line
from proto.cli_pb2_grpc import add_cliServicer_to_server, cliServicer


class StdinPipe(Thread):
    def __init__(self, buffer: Line, pipe: int) -> None:
        self.buffer = buffer
        self.pipe = pipe
        super().__init__()
        self.start()

    def run(self):
        for line in self.buffer:
            os.write(self.pipe, line.buffer.encode())


class Server(cliServicer):
    def call(self, lines, context):
        try:
            # read first line as it contains the command to execute
            cmd = split(next(lines).buffer)

            process_master_pty, process_follower_pty = pty.openpty()
            stdin_master_pty, stdin_follower_fd = pty.openpty()

            tty.setraw(stdin_follower_fd)

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
                        yield Line(buffer=os.read(process_master_pty, 10240))

        except Exception as e:
            print(f"error at {e}")
            import traceback

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
