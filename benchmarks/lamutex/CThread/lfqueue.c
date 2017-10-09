#include <pthread.h>
#include <stdlib.h>
#include "lfqueue.h"


pthread_mutex_t q_mutex;

lfqueue_t*
lfqueue_create () {
#ifdef LFQ
	lfqueue_t* lq = (lfqueue_t*) malloc(sizeof(lfqueue_t));
	pthread_mutex_init(&lq->mutex, NULL);
	lq->q = q_initialize();
	return lq;
#endif
}

void
lfqueue_free (lfqueue_t* lq) {
#ifdef LFQ
	pthread_mutex_lock(&lq->mutex);
	queue_free(lq->q);
	pthread_mutex_unlock(&lq->mutex);
	pthread_mutex_destroy(&lq->mutex);
	free(lq);
#endif
}

void
lfqueue_enqueue (lfqueue_t* lq, void* val) {
#ifdef LFQ
	pthread_mutex_lock(&lq->mutex);
	qpush(lq->q, val);
	pthread_mutex_unlock(&lq->mutex);
#endif
}

void*
lfqueue_dequeue (lfqueue_t* lq) {
#ifdef LFQ
	pthread_mutex_lock(&lq->mutex);
	void* d = qpop(lq->q, (long) pthread_self());
	pthread_mutex_unlock(&lq->mutex);
	return d;
#endif
}
