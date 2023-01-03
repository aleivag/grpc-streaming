package main

import (
	"bufio"
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"syscall"

	cli "github.com/aleivag/grpc-streaming/proto"
	"github.com/pkg/term/termios"
	"golang.org/x/sys/unix"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

var (
	addr = flag.String("addr", "localhost:50051", "the address to connect to")
)

func SetRaw(fd uintptr) (unix.Termios, error) {
	var oldstate unix.Termios
	if err := termios.Tcgetattr(fd, &oldstate); err != nil {
		return oldstate, err
	}
	newstate := oldstate

	newstate.Iflag &^= syscall.ISTRIP | syscall.INLCR | syscall.ICRNL | syscall.IGNCR | syscall.IXON | syscall.IXOFF
	newstate.Lflag &^= syscall.ECHO | syscall.ICANON | syscall.ISIG

	termios.Tcsetattr(fd, termios.TCSAFLUSH, &newstate)

	return oldstate, nil

}

func main() {

	conn, err := grpc.Dial(*addr, grpc.WithTransportCredentials(insecure.NewCredentials()))

	if err != nil {
		log.Fatalf("did not connect: %v", err)
	}

	defer conn.Close()

	client := cli.NewCliClient(conn)

	stream, err := client.Call(context.Background())
	stdoutchan := make(chan struct{})
	stdinchan := make(chan string)

	go func() {
		defer close(stdoutchan)
		for {
			reply, err := stream.Recv()
			if err == io.EOF {
				return
			}
			if err != nil {
				log.Fatalf("Error when receiving response: %v", err)
				return
			}
			fmt.Print(reply.Buffer)

		}

	}()

	go func() {
		oldstate, _ := SetRaw(0)
		defer termios.Tcgetattr(0, &oldstate)
		defer close(stdinchan)

		reader := bufio.NewReader(os.Stdin)
		for {
			char, _, err := reader.ReadRune()
			if err != nil {
				log.Fatal(err)
			}
			stdinchan <- string(char)

		}

	}()

	line := &cli.Line{Buffer: "/bin/bash"}
	if err := stream.Send(line); err != nil {
		log.Fatalf("%v.Send(%v) = %v", stream, line, err)
	}

	finished := false

	for !finished {
		select {
		case char := <-stdinchan:
			senderr := stream.Send(&cli.Line{Buffer: string(char)})

			if senderr == io.EOF {
				finished = true
			}
		case <-stdoutchan:
			finished = true
		}
	}

}
