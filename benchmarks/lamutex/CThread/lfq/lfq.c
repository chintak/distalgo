#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "lfq.h"

#define CAS(ptr, oval, nval)						\
	(unsigned) __sync_bool_compare_and_swap((ptr), (oval), (nval))

ushort_t
new_node(shared_mem_t* smp) {
	unsigned success;
	ushort_t node, newfree;

	for (success = FALSE; success == FALSE; ) {
		node = smp->freeidx;
		newfree = smp->nodes[node].next.sep.ptr;
		success = CAS(&smp->freeidx, node, newfree);
	}
//	printf("(new %d) ", node);
	return node;
}

void
reclaim(shared_mem_t* smp, ushort_t node) {
	ushort_t curfree;
	unsigned success;

	for (success = FALSE; success == FALSE; ) {
		curfree = smp->freeidx;
		success = CAS(&smp->freeidx, curfree, node);
	}
	smp->nodes[node].next.sep.ptr = curfree;
//	printf("(free %d) ", node);
}

void
init_queue(shared_mem_t* smp, int max_nodes)
{
	unsigned i;
	/* init node free list */
	if (!smp->nodes) {
		smp->nodes = (node_t*) malloc((max_nodes+1) * sizeof(node_t));
	}

	/* initialize queue */
	smp->head.sep.ptr = 1;
	smp->head.sep.count = 0;
	smp->tail.sep.ptr = 1;
	smp->tail.sep.count = 0;
	smp->nodes[1].next.sep.ptr = NULL;
	smp->nodes[1].next.sep.count = 0;

	/* initialize avail list */
	for (i=2; i<max_nodes; i++) {
		smp->nodes[i].next.sep.ptr = i+1;
		smp->nodes[i].next.sep.count = 0;
	}
	smp->nodes[max_nodes].next.sep.ptr = NULL;
	smp->nodes[max_nodes].next.sep.count = 0;

	smp->freeidx = 2;
}

void
enqueue(shared_mem_t* smp, void* val)
{
	unsigned success;
	ushort_t node;
	pointer_t tail;
	pointer_t next;

	node = new_node(smp);
	smp->nodes[node].value = val;
	smp->nodes[node].next.sep.ptr = NULL;

//	backoff = backoff_base;
	for (success = FALSE; success == FALSE; ) {
		tail.con = smp->tail.con;
		next.con = smp->nodes[tail.sep.ptr].next.con;
		if (tail.con == smp->tail.con) {
			if (next.sep.ptr == NULL) {
//				backoff = backoff_base;
				success = CAS(
					(ulong_t*) &smp->nodes[tail.sep.ptr].next,
					next.con,
					MAKE_LONG(node, next.sep.count+1));
			}
			if (success == FALSE) {
				CAS((ulong_t*) &smp->tail,
				    tail.con,
				    MAKE_LONG(smp->nodes[tail.sep.ptr].next.sep.ptr,
					      tail.sep.count+1));
//				backoff_delay();
			}
		}
	}
	success = CAS((ulong_t*) &smp->tail,
		      tail.con,
		      MAKE_LONG(node, tail.sep.count+1));
	return;  // REMOVE
}

void*
dequeue(shared_mem_t* smp)
{
	void* value;
	unsigned success;
	pointer_t head;
	pointer_t tail;
	pointer_t next;

//	backoff = backoff_base;
	for (success = FALSE; success == FALSE; ) {
		head.con = smp->head.con;
		tail.con = smp->tail.con;
		next.con = smp->nodes[head.sep.ptr].next.con;
		if (smp->head.con == head.con) {
			if (head.sep.ptr == tail.sep.ptr) {
				if (next.sep.ptr == NULL) {
					return nullptr;
				}
				CAS((ulong_t*) &smp->tail,
				    tail.con,
				    MAKE_LONG(next.sep.ptr, tail.sep.count+1));
//				backoff_delay();
			} else {
				value = smp->nodes[next.sep.ptr].value;
				success = CAS((ulong_t*) &smp->head,
					      head.con,
					      MAKE_LONG(next.sep.ptr, head.sep.count+1));
				if (success == FALSE) {
//					backoff_delay();
				}
			}
		}
	}
	reclaim(smp, head.sep.ptr);
	return value;
}


void
cleanup(shared_mem_t* smp) {
	if (smp->nodes) free(smp->nodes);
}
