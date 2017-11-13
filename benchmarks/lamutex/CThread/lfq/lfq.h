/*
 * ORIGINAL
 * Author: Prof Michael Scott
 * The following lock free queue implementation was provided by Prof Michael Scott.
 * It can be found under "new" folder in from http://www.cs.rochester.edu/research/synchronization/code/concurrent_queues/SGI.tgz.
 *
 * MODIFICATION
 * Author: Chintak Sheth
 * The necessary changes are indicated appropriately in comments alongside the functions.
 */
#ifndef __LFQ_H_
#define __LFQ_H_

#include <stdint.h>

#define TRUE				1
#define FALSE				0
#ifdef NULL
#undef NULL
#endif
#define NULL				0
#define nullptr 			((void*) 0)  /* Modified: added */

/* Modified: original code made use of `unsigned short` and `unsigned long` and the
 * MAKE_LONG assumed a 32-bit architecture.
 * We added architecture check to define `ulong_t` and `ushort_t` correctly.
 */
// Check GCC
#if __GNUC__
#if __x86_64__ || __ppc64__
// 64 bit architecture
#define ushort_t 			uint32_t
#define ulong_t 			uint64_t
#define MAKE_LONG(hi, lo)		((ulong_t)(hi)<<32)+(lo)
//#define MAX_NODES			0xffff
#else
// 32 bit architecture
#define ushort_t 			uint16_t
#define ulong_t 			uint32_t
#define MAKE_LONG(hi, lo)		((ulong_t)(hi)<<16)+(lo)
//#define MAX_NODES			0xff
#endif
#endif

typedef union pointer {
	struct {
		volatile ushort_t count;
		volatile ushort_t ptr;
	} sep;
	volatile ulong_t con;
}pointer_t;

typedef struct node {
	void* value;  /* Modified: changed value type from `unsigned` to `void*` */
	pointer_t next;
	// unsigned foo[30];  /* Modified: commented out */
} node_t;

/* Modified: commented out
typedef struct private {
	unsigned node;
	unsigned value;
	unsigned serial[MAX_SERIAL];
} private_t;
*/

typedef struct shared_mem {
	pointer_t head;
	// unsigned foo1[31];  /* Modified: commented out */
	pointer_t tail;
	// unsigned foo2[31];  /* Modified: commented out */
	node_t* nodes;  /* Modified: use pointer type instead of array */
	ushort_t freeidx;  /* Modified: rename `serial` to `freeidx` */
} shared_mem_t;


void init_queue(shared_mem_t* smp, int max_nodes);
void enqueue(shared_mem_t* smp, void* val);
void* dequeue(shared_mem_t* smp);
void cleanup(shared_mem_t* smp);

#endif
