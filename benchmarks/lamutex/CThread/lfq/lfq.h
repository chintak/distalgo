#ifndef __LFQ_H_
#define __LFQ_H_

#include <stdint.h>

#define TRUE				1
#define FALSE				0
#ifdef NULL
#undef NULL
#endif
#define NULL				0
#define nullptr 			((void*) 0)

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
	void* value;
	pointer_t next;
} node_t;

typedef struct shared_mem {
	pointer_t head;
	pointer_t tail;
	node_t* nodes;
	ushort_t freeidx;
} shared_mem_t;


void init_queue(shared_mem_t* smp, int max_nodes);
void enqueue(shared_mem_t* smp, void* val);
void* dequeue(shared_mem_t* smp);
void cleanup(shared_mem_t* smp);

#endif
