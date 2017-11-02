#define _POSIX_SOURCE
#define _GNU_SOURCE

#include <signal.h>
#include <errno.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <pthread.h>
#include <sched.h>
#include <time.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/time.h>
#include <sys/resource.h>

#include "lfqueue.h"

#define MAX(a, b) 	(((a) > (b)) ? (a) : (b))
#define ERRMSG(str) 	{ printf("%s:%s:%d: Error - %s\n",		\
				 __FILE__, __func__, __LINE__, str); goto cleanup; }
#define MPANIC(a) 	if ((a) == NULL) ERRMSG("malloc failed");
#define NZPANIC(a) 	if ((a)) ERRMSG(strerror((a)));

#define THR_ERRMSG(str) {						\
		printf("%s:%s:%d: Error - %s\n",			\
		       __FILE__, __func__, __LINE__, str);		\
		pthread_exit(NULL); }
#define THR_MPANIC(a) 	if ((a) == NULL) THR_ERRMSG("thread malloc failed");
#define THR_NZPANIC(a) 	if ((a)) THR_ERRMSG(strerror((a)));

#define DEBUG
#define DPRINT(a) 	if (DEBUG==1) { a; }

/***** Data Structures *****/

#define MAX_MSG_PER_WORKER 5

typedef int pid_t;

typedef enum _message {
	NONE = 0,
	REQUEST = 1,
	RELEASE = 2,
	ACK = 3,
	DONE = 4,
	START = 5
} msg_t;

typedef struct _packet {
	long clock;
	pid_t id;
	msg_t type;
} pkt_t;

typedef struct _peer {
	long clock;
	pid_t id;
	int req;
} peer_t;

typedef struct _worker_memory {
	long clock;
	pid_t id;

	lfqueue_t* qmsg;
	peer_t* peers_req;
	int* acks;
	pid_t nacks;

	int start;
	int done;
	short num_rounds;
	struct timeval usrtime;
	struct timeval systime;
} mem_t;

typedef int (*await_cond_func)(mem_t* m);

static const pid_t BROADCAST = -1;

/***** Globals *****/

pthread_t* workers;
pid_t num_workers;
mem_t* wk_mems;

pid_t num_init;
pthread_mutex_t num_init_mutex;
pthread_cond_t num_init_cv;

pid_t num_done;
pthread_mutex_t num_done_mutex;
pthread_cond_t num_done_cv;

/***** Forward declarations *****/

void await(await_cond_func test, mem_t* m);
void yield(mem_t* m, int block);

void send_message(pid_t to, msg_t type, mem_t* m);

int handle_start_cond(mem_t* m);
int handle_done_cond(mem_t* m);
int handle_message(mem_t* m);

void tv_sub(struct timeval *tva, struct timeval *tvb);
void collect_usage_stats ();

static void core_dump(int sigid) {
	kill(getpid(), SIGSEGV);
}

/***** Server functions *****/

void
setup_worker_memory (short nrounds) {
	// alloc worker memory for `num_workers` and set id & num_rounds
	wk_mems = (mem_t*) malloc(num_workers * sizeof(mem_t)); THR_MPANIC(wk_mems);
	for (int i = 0; i < num_workers; i++) {
		wk_mems[i].id = i;
		wk_mems[i].num_rounds = nrounds;
		wk_mems[i].start = 0;
		wk_mems[i].done = 0;
	}
}

void
server_loop () {
	// broadcast START
	// block & check for all the workers to complete num_rounds
	// broadcast DONE
	pthread_mutex_lock(&num_init_mutex);
	while (num_init < num_workers) {
		pthread_cond_wait(&num_init_cv, &num_init_mutex);
	}
	pthread_mutex_unlock(&num_init_mutex);

	send_message(BROADCAST, START, NULL);

	pthread_mutex_lock(&num_done_mutex);
	while (num_done < num_workers) {
		pthread_cond_wait(&num_done_cv, &num_done_mutex);
	}
	pthread_mutex_unlock(&num_done_mutex);

	send_message(BROADCAST, DONE, NULL);
	// collect stats
	collect_usage_stats();
}

/***** Critical Section *****/

int
peercmp (peer_t* p1, peer_t* p2) {
	return (p1->clock < p2->clock ||
		(p1->clock == p2->clock && p1->id < p2->id));
}

peer_t*
minpeer (mem_t* m) {
	peer_t* mpeer = NULL;
	for (int i = 0; i < num_workers; i++) {
		if (m->peers_req[i].req &&
		    (!mpeer || peercmp((m->peers_req + i), mpeer)))
			mpeer = m->peers_req + i;
	}
	return mpeer;
}

int
enter_cs_cond (mem_t* m) {
	peer_t* mpeer = minpeer(m);
	return (m->nacks == num_workers) && mpeer && (mpeer->id == m->id);
}

void
enter_critical_section (mem_t* m) {
	// clear acks
	// broadcast REQUEST
	// await till permission granted
	memset((void*) m->acks, 0, num_workers * sizeof(int));
	m->nacks = 0;
	send_message(BROADCAST, REQUEST, m);
	await(enter_cs_cond, m);
}

void
leave_critical_section (mem_t* m) {
	// clear req
	// broadcast RELEASE
	send_message(BROADCAST, RELEASE, m);
}

/***** Worker functions *****/

void
yield (mem_t* m, int block) {
	// TODO: try to handle msgs a small # of times
	// (instead of once) before yielding control.
	// Nothing will change without any external message,
	// so we block till we handle at least one message.
	if (!block)
		handle_message(m);
	else {
		while (!handle_message(m)) sched_yield();
	}
}

void
await (await_cond_func test, mem_t* m) {
	// sleep instead of yielding to sched
	while (!test(m)) /* block */ {
		yield(m, 1);
	}
}

int
handle_start_cond (mem_t* m) {
	// server will set the `start` flag
	// check if the flag is set
	return m->start;
}

int
handle_done_cond (mem_t* m) {
	// server will set the `done` flag
	// free worker memory and return
	if (m->done == num_workers) {
		// free memory
		if (m->qmsg) lfqueue_free(m->qmsg);
		if (m->peers_req) free(m->peers_req);
		if (m->acks) free(m->acks);
	}
	return (m->done == num_workers);
}

void
init_self_worker_mem (mem_t* m) {
	m->clock = 0;
	m->qmsg = lfqueue_create(num_workers * MAX_MSG_PER_WORKER);
	m->peers_req = (peer_t*) malloc(num_workers * sizeof(peer_t));
	for (int i = 0; i < num_workers; i++) {
		m->peers_req[i].id = i;
		m->peers_req[i].clock = 0;
		m->peers_req[i].req = 0;
	}
	m->acks = (int*) malloc(num_workers * sizeof(int));
	memset((void*) m->acks, 0, num_workers * sizeof(int));
	m->nacks = 0;
	m->start = 0;
	// id, num_rounds, done set by server
	pthread_mutex_lock(&num_init_mutex);
	num_init++;
	if (num_init == num_workers) {
		pthread_cond_signal(&num_init_cv);
	}
	pthread_mutex_unlock(&num_init_mutex);
}

void
worker_done (mem_t* m, struct rusage* rudata_start, struct rusage* rudata_end) {
	// worker done
	tv_sub(&rudata_end->ru_utime, &rudata_start->ru_utime);
	tv_sub(&rudata_end->ru_stime, &rudata_start->ru_stime);
	m->usrtime = rudata_end->ru_utime;
	m->systime = rudata_end->ru_stime;

	pthread_mutex_lock(&num_done_mutex);
	num_done++;
	if (num_done == num_workers) {
		pthread_cond_signal(&num_done_cv);
	}
	pthread_mutex_unlock(&num_done_mutex);
}

void
*worker_main_loop (void* _mem) {
	int count = 0;
	mem_t* m = (mem_t*) _mem;
	struct rusage rudata_start, rudata_end;

	init_self_worker_mem(m);
	await(handle_start_cond, m);
	getrusage(RUSAGE_THREAD, &rudata_start);

	while (count < m->num_rounds) {
//		yield(m, 0);

		// Enter critical section
		enter_critical_section(m);

		printf("P%d is in CS with clock %ld\n", m->id, m->clock);
		fflush(stdout);
//		yield(m, 0);

		printf("P%d is leaving CS - %d\n", m->id, count);
		fflush(stdout);
		leave_critical_section(m);

		fflush(stdout);
		count++;
	}

	getrusage(RUSAGE_THREAD, &rudata_end);
	worker_done(m, &rudata_start, &rudata_end);
	await(handle_done_cond, m);

	pthread_exit(NULL);
}

/***** Messaging *****/

void
send_message (pid_t to, msg_t type, mem_t* m) {
	// send msg from a worker to others - REQUEST, RELEASE
	// push the message to msg q of all worker threads

	// free packet on dequeue
	pkt_t* packet = (pkt_t*) malloc(sizeof(pkt_t));
	if (!m) {
		packet->id = BROADCAST;
		packet->clock = 0;
	} else {
		packet->id = m->id;
		packet->clock = m->clock;
	}
	packet->type = type;

	if (to == BROADCAST) {  // send to self also
		for (int i = 0; i < num_workers; i++) {
			void* dpkt = malloc(sizeof(pkt_t));
			memcpy(dpkt, (void*) packet, sizeof(pkt_t));
			lfqueue_enqueue(wk_mems[i].qmsg, dpkt);
		}
		free(packet);
	} else {
		lfqueue_enqueue(wk_mems[to].qmsg, (void*) packet);
	}
}

int
handle_message (mem_t* m) {
	// handle RELEASE, REQUEST messages
	// return 1 if msg handled, else returns 0
	pkt_t* d = (pkt_t*) lfqueue_dequeue(m->qmsg);
	if (!d) return 0;
	pid_t from = d->id;

	switch (d->type) {
	case REQUEST:
		m->peers_req[from].req = 1;
		m->peers_req[from].clock = d->clock;
		m->clock = MAX(m->clock, d->clock) + 1;
		send_message(from, ACK, m);
		break;

	case RELEASE:
		m->peers_req[from].req = 0;
		break;

	case START:
		m->start = 1;
		m->clock = 0;
		break;

	case DONE:
		m->done = num_workers;
		break;

	case ACK:
		if (!m->acks[from]) {
			m->acks[from] = 1;
			m->nacks++;
		}

	default:
		break;
	}

	//if (d) free(d);
	return 1;
}

/***** Main *****/

int
main (int argc, char** argv) {
	int rc;
	void* status;
	short nrounds;
	pthread_attr_t attr;
	/* Initialize mutex and condition variable objects */
	pthread_mutex_init(&num_init_mutex, NULL);
	pthread_mutex_init(&num_done_mutex, NULL);
	pthread_cond_init (&num_init_cv, NULL);
	pthread_cond_init (&num_done_cv, NULL);
	pthread_attr_init(&attr);
	pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_JOINABLE);

	// DEBUG - generate core dump file on ^C
	signal(SIGINT, core_dump);

	num_workers = 5;
	nrounds = 1;
	if (argc > 1) num_workers = atoi(argv[1]);
	if (argc > 2) nrounds = atoi(argv[2]);

	// create workers and assign work
	workers = (pthread_t*) malloc(num_workers * sizeof(pthread_t));
	MPANIC(workers);
	setup_worker_memory(nrounds);

	for (uint64_t i = 0; i < num_workers; i++) {
		rc = pthread_create(workers + i, &attr,
				    worker_main_loop, (void*) (wk_mems + i));
		NZPANIC(rc);
	}

	server_loop();

	// join and terminate workers
	for (int i = 0; i < num_workers; i++) {
		rc = pthread_join(workers[i], &status);
	}
	pthread_attr_destroy(&attr);
	pthread_mutex_destroy(&num_init_mutex);
	pthread_mutex_destroy(&num_done_mutex);
	pthread_cond_destroy(&num_init_cv);
	pthread_cond_destroy(&num_done_cv);

cleanup:
	if (workers) free(workers);
	if (wk_mems) free(wk_mems);
	pthread_exit(NULL);
	return 0;
}

/* ********** Auxiliary functions **********  */

void tv_add(struct timeval *tva, struct timeval *tvb)
{
    tva->tv_sec += tvb->tv_sec;
    tva->tv_usec += tvb->tv_usec;
    if (tva->tv_usec > 1000000) {
        tva->tv_usec %= 1000000;
        tva->tv_sec ++;
    }
}

void tv_sub(struct timeval *tva, struct timeval *tvb)
{
    tva->tv_sec -= tvb->tv_sec;
    tva->tv_usec -= tvb->tv_usec;
    if (tva->tv_usec < 0) {
        tva->tv_usec += 1000000;
        tva->tv_sec --;
    }
}

void
collect_usage_stats () {
	struct timeval usrtime, systime;
	for (int i = 0; i < num_workers; i++) {
		tv_add(&usrtime, &wk_mems[i].usrtime);
		tv_add(&systime, &wk_mems[i].systime);
	}
	tv_add(&systime, &usrtime);

	printf("###OUTPUT: {\"Total_processes\": %d,    \
\"Total_process_time\": %ld.%06ld,			\
\"Total_user_time\": %ld.%06ld}\n",
	       num_workers,
	       systime.tv_sec, (long) systime.tv_usec,
	       usrtime.tv_sec, (long) usrtime.tv_usec);
}
