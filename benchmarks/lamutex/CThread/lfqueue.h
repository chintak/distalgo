#ifndef __LFQUEUE_H_
#define __LFQUEUE_H_

// #define SLQ  // single lock q
// #define LFQ  // lock free q by Michael and Scott

#ifdef SLQ
#include <pthread.h>
#include "slq.h"

// typedef Queue lfqueue_t;
typedef struct _ {
	Queue* q;
	pthread_mutex_t mutex;
} lfqueue_t;
#endif  // end SLQ

#ifdef LFQ
#include "lfq.h"

typedef shared_mem_t lfqueue_t;
#endif  // end LFQ


lfqueue_t* 	lfqueue_create ();
void 		lfqueue_enqueue (lfqueue_t* q, void* val);
void*	 	lfqueue_dequeue (lfqueue_t* q);
void	 	lfqueue_free (lfqueue_t* q);

#endif
