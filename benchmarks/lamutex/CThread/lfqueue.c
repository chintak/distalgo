#include <pthread.h>
#include <stdlib.h>
#include "lfqueue.h"

#if !defined(LFQ) && !defined(SLQ)
#error "Queue backend not defined. Define LFQ or SLQ."
#endif

pthread_mutex_t q_mutex;

lfqueue_t*
lfqueue_create (int max_nodes) {
#ifdef SLQ
	lfqueue_t* lq = (lfqueue_t*) malloc(sizeof(lfqueue_t));
	pthread_mutex_init(&lq->mutex, NULL);
	lq->q = q_initialize();
	return lq;
#endif
#ifdef LFQ
	lfqueue_t* lq = (lfqueue_t*) malloc(sizeof(lfqueue_t));
	init_queue(lq, max_nodes);
	return lq;
#endif
}

void
lfqueue_free (lfqueue_t* lq) {
#ifdef SLQ
	pthread_mutex_lock(&lq->mutex);
	queue_free(lq->q);
	pthread_mutex_unlock(&lq->mutex);
	pthread_mutex_destroy(&lq->mutex);
	free(lq);
#endif
#ifdef LFQ
	cleanup(lq);
	free(lq);
#endif
}

void
lfqueue_enqueue (lfqueue_t* lq, void* val) {
#ifdef SLQ
	pthread_mutex_lock(&lq->mutex);
	qpush(lq->q, val);
	pthread_mutex_unlock(&lq->mutex);
#endif
#ifdef LFQ
	enqueue(lq, val);
#endif
}

void*
lfqueue_dequeue (lfqueue_t* lq) {
#ifdef SLQ
	pthread_mutex_lock(&lq->mutex);
	void* d = qpop(lq->q, (long) pthread_self());
	pthread_mutex_unlock(&lq->mutex);
	return d;
#endif
#ifdef LFQ
	return dequeue(lq);
#endif
}
