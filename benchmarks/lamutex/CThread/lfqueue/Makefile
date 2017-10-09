test:
	gcc -g test.c lfq.c -o test -lpthread

all:
	gcc -g3 -O0 -o lfq.o -c lfq.c -lpthread -fPIC
	gcc -g3 -O0 -shared -o liblfq.so lfq.o -fPIC
	ln -sf `pwd`/liblfq.so ../

clean:
	rm -rf test liblfq.so *.o
