#ifndef __LFQUEUE_H_
#define __LFQUEUE_H_

#include <pthread.h>

#include "lfq.h"

#define LFQ

#ifdef LFQ
// typedef Queue lfqueue_t;
typedef struct _ {
	Queue* q;
	pthread_mutex_t mutex;
} lfqueue_t;
#endif  // end QUEUE_BACKEND


lfqueue_t* 	lfqueue_create ();
void 		lfqueue_enqueue (lfqueue_t* q, void* val);
void*	 	lfqueue_dequeue (lfqueue_t* q);
void	 	lfqueue_free (lfqueue_t* q);

#endif
