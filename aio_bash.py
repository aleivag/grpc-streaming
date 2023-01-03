#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Dont kjnow who this would help, but this explain how to "shell out" to bash with 
multiplexing using asyncio in python... just for fun
"""

import os
import pty
import select
import sys
import termios
import tty
from subprocess import Popen

import click
import asyncio
from functools import wraps


def syncify(fnc):
    @wraps(fnc)
    def _(*a, **b):
        return asyncio.run(fnc(*a, **b))

    return _


def fd2fd(fdo, fdd):
    if o := os.read(fdo, 10240):
        os.write(fdd, o)


@click.command()
@click.argument("shell", default="bash")
@syncify
async def bash(shell):
    command = [shell]  # "bash"

    old_tty = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin.fileno())

    loop = asyncio.get_running_loop()

    # open pseudo-terminal to interact with subprocess
    master_fd, follower_fd = pty.openpty()

    loop.add_reader(master_fd, fd2fd, master_fd, sys.stdout.fileno())
    loop.add_reader(sys.stdin.fileno(), fd2fd, sys.stdin.fileno(), master_fd)

    p = await asyncio.subprocess.create_subprocess_exec(
        *command,
        stdin=follower_fd,
        stdout=follower_fd,
        stderr=follower_fd,
    )
    estatus = await p.wait()

    loop.remove_reader(master_fd)
    loop.remove_reader(sys.stdin.fileno())

    # restore tty settings back
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)
    return estatus


if __name__ == "__main__":
    the_bash = bash()
    exitv = asyncio.run(the_bash)
