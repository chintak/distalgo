CC=gcc-5
CFLAGS=-g -O0 -Wall -Werror
INCFLAGS=-I./lfqueue
LDFLAGS=-L./lfqueue
LIBS=-llfq -lpthread

all : lamutex
#	strip lamutex

%.o : %.c
	$(CC) $(CFLAGS) $(INCFLAGS) -c  $<

lamutex : lamutex.o lfqueue.o
	$(CC) $(LDFLAGS) -o lamutex $^ $(LIBS)

test_slqueue : slqueue.o test_slqueue.o
	$(CC) $(LDFLAGS) -o test_slqueue $^ -lpthread

test_myq : myqueue.o test_myqueue.o
	$(CC) -g -O0 -o test_myq $^ -lpthread

clean :
	rm -f *.o lamutex test_slqueue mtest_myq

.PHONY : all clean
