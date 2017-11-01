test:
	gcc -g test.c slq.c -o test -lpthread

all:
	gcc -g3 -O0 -o slq.o -c slq.c -lpthread -fPIC
	gcc -g3 -O0 -shared -o libslq.so slq.o -fPIC
	ln -sf `pwd`/libslq.so ../

clean:
	rm -rf test libslq.so *.o
