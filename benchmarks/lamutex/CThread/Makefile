ifndef ${Q}
	Q=LFQ
endif

CC=gcc
ifndef ${DEBUG}
	CFLAGS= -std=c99 -O3 -Wall -Werror -D${Q}  # -DSLQ or -DLFQ
else
	CFLAGS= -std=c99 -g3 -O0 -Wall -Werror -D${Q}
endif
INCFLAGS= -I./lfq  -I./slq
LDFLAGS=  -L./lfq  -L./slq
LIBS=-lslq -llfq -lpthread

all : lamutex
#	strip lamutex

%.o : %.c
	$(CC) $(CFLAGS) $(INCFLAGS) -c  $<

queues :
	make -C slq all
	make -C lfq all

lamutex : lamutex.o lfqueue.o
	$(CC) $(LDFLAGS) -o lamutex $^ $(LIBS)

# test_slqueue : slqueue.o test_slqueue.o
# 	$(CC) $(LDFLAGS) -o test_slqueue $^ -lpthread

# test_myq : myqueue.o test_myqueue.o
# 	$(CC) -g -O0 -o test_myq $^ -lpthread

clean :
	rm -f *.o lamutex test_slqueue test_myq

.PHONY : all clean
