#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>

#include "lfq.h"

#define PRODUCERS 20000
#define CONSUMERS 1

#define nullptr ((void*) 0)

int done;

typedef struct _elem {
	int val;
	int pid;
} elem_t;

typedef struct _thread_dat {
	shared_mem_t* smp;
	int pid;
} thread_data_t;


void
printq(shared_mem_t* smp) {
	unsigned int it = smp->head.sep.ptr;
	elem_t* d;
	ushort_t v = 0, p = 0;
	int c = PRODUCERS + 2;
	while (it != smp->tail.sep.ptr) {
		v = 0, p = 0;
		d = (elem_t*) smp->nodes[it].value;
		if (d) { v = d->val; p = d->pid; }
		printf("[%d-%d|%d] -> ",
		       v, p, smp->nodes[it].next.sep.ptr);
		it = smp->nodes[it].next.sep.ptr;
		if (!--c) break;
	}
	v = 0, p = 0;
	d = (elem_t*) smp->nodes[it].value;
	if (d) { v = d->val; p = d->pid; }
	printf("[%d-%d|%d] -> ",
	       v, p, smp->nodes[it].next.sep.ptr);
	printf("NULL\n");
	fflush(stdout);
}

void
printn(shared_mem_t* smp) {
	unsigned int i;
	elem_t* d;
	printf("head: %d; tail: %d ", smp->head.sep.ptr, smp->tail.sep.ptr);
	for (i = 0; i < PRODUCERS+1; i++) {
		d = (elem_t*) smp->nodes[i].value;
		if (d)
			printf("%d[%d-%d|%d] -> ", i, d->val, d->pid,
			       smp->nodes[i].next.sep.ptr);
		else
			printf("%d[%d-%d|%d] -> ", i, 0, 0,
			       smp->nodes[i].next.sep.ptr);
	}
	printf("NULL\n");
	fflush(stdout);
}


void
printl(shared_mem_t* smp) {
	unsigned int i;
	ushort_t it = smp->freeidx;
	printf("head: %d tail: %d freeidx: ", smp->head.sep.ptr, smp->tail.sep.ptr);
	for (i = 0; i < PRODUCERS+2; i++) {
		printf("%d -> ", it);
		it = smp->nodes[it].next.sep.ptr;
	}
	printf("NULL\n");
	fflush(stdout);
}


void
*producer(void* d) {
	unsigned int i;
	thread_data_t* m = (thread_data_t*) d;
	elem_t* data;
	__sync_synchronize();
	for (i = 0; i < 1; i++) {
		data = (elem_t*) malloc(sizeof(elem_t));
		data->val = 1000+i;
		data->pid = m->pid;
		enqueue(m->smp, (void*) data);
		printf("p%d pushed %d\n", m->pid, data->val);
		fflush(stdout);
	}
	pthread_exit(NULL);
}


void
*consumer(void* d) {
	thread_data_t* m = (thread_data_t*) d;
	elem_t* data;
	while (!done) {
		data = (elem_t*) dequeue(m->smp);
		if (!data) continue;
		printf("p%d dequeued p%d's %d\n", m->pid, data->pid, data->val);
//		printn(m->smp);
		free(data);
	}
//	printn(m->smp);
	pthread_exit(NULL);
}


int
main(int argc, char** argv) {
	int rc;
	void* status;
	unsigned int i;
	pthread_t workers[PRODUCERS+CONSUMERS];
	thread_data_t tdatas[PRODUCERS+CONSUMERS];
	shared_mem_t* smp = (shared_mem_t*) malloc(sizeof(shared_mem_t));

	done = 0;
	init_queue(smp, PRODUCERS*5);
	printl(smp);
	// init producers
	for (i = 0; i < PRODUCERS; i++) {
		tdatas[i].smp = smp;
		tdatas[i].pid = i;
	}
	// init consumers
	for (; i < PRODUCERS+CONSUMERS; i++) {
		tdatas[i].smp = smp;
		tdatas[i].pid = 100 + i;
	}

	// allocate work
	for (i = 0; i < PRODUCERS; i++) {
		pthread_create(workers + i, NULL, producer, (void*) (tdatas+i));
	}
	for (i = 0; i < PRODUCERS; i++) {
		rc = pthread_join(workers[i], &status);
	}

	printq(smp);

	for (i = PRODUCERS; i < PRODUCERS+CONSUMERS; i++) {
		pthread_create(workers + i, NULL, consumer, (void*) (tdatas+i));
	}
	sleep(2);
	done = 1;
	for (i = PRODUCERS; i < PRODUCERS+CONSUMERS; i++) {
		rc = pthread_join(workers[i], &status);
	}
	printl(smp);
	pthread_exit(NULL);
	return 0;
}
