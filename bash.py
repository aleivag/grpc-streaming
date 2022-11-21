#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import pty
import select
import sys
import termios
import tty
from subprocess import Popen

import click


@click.command()
@click.argument("shell", default="bash")
def bash(shell):
    command = shell  # "bash"

    old_tty = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin.fileno())

    # open pseudo-terminal to interact with subprocess
    master_fd, follower_fd = pty.openpty()

    with Popen(
        command,
        preexec_fn=os.setsid,
        stdin=follower_fd,
        stdout=follower_fd,
        stderr=follower_fd,
        universal_newlines=True,
        bufsize=0,
    ) as p:
        while p.poll() is None:
            r, w, e = select.select([sys.stdin, master_fd], [], [])
            if sys.stdin in r:
                d = os.read(sys.stdin.fileno(), 10240)
                os.write(master_fd, d)
            elif master_fd in r:
                o = os.read(master_fd, 10240)
                if o:
                    os.write(sys.stdout.fileno(), o)

    # restore tty settings back
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)
    return p.wait()


if __name__ == "__main__":
    exitv = bash()
    print(exitv)
    sys.exit(exitv)
