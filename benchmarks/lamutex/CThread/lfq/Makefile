LDFLAGS = -lm

all:
	gcc -g3 -O2 -o lfq.o -c lfq.c $(LDFLAGS) -fPIC
	gcc -g3 -O2 -shared -o liblfq.so lfq.o -fPIC
	ln -sf `pwd`/liblfq.so ../

test:
	gcc -g3 -O0 -o lfq.o -c lfq.c -lpthread $(LDFLAGS)
	gcc -g3 -O0 -o test.o -c test.c -lpthread $(LDFLAGS)
	gcc -g3 -O0 -o test test.o lfq.o -lpthread $(LDFLAGS)

clean:
	rm -f *.o liblfq.so *~ core test
