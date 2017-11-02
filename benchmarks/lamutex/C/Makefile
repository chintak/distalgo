
CC=gcc
CFLAGS=-O3 -std=c99 -fms-extensions -D_POSIX_C_SOURCE=199309L -D_DARWIN_C_SOURCE
LDFLAGS=

all : lamport
	strip lamport

lamport : lamport.o pqueue.o

clean :
	rm -f *.o lamport

.PHONY : all clean
