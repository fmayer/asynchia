#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/socket.h>

static size_t asynchia_minsize(size_t a, size_t b) {
	if (a < b) {
		return a;
	}
	return b;
}

struct asynchia_send_ret {
	size_t ret;
	int errsv;
};

struct asynchia_buffer {
	size_t size;
	size_t length;
	size_t position;
	char* buf;
};

int asynchia_buffer_expand(struct asynchia_buffer* buf, size_t n) {
	char* nbuf = realloc(buf->buf, buf->length + n);
	if (nbuf != NULL) {
		buf->buf = nbuf;
		buf->length = buf->length + n;
		return 0;
	} else {
		return -1;
	}
}

struct asynchia_buffer* asynchia_buffer_new(size_t length) {
	struct asynchia_buffer* nbuf = malloc(sizeof(struct asynchia_buffer));
	if (nbuf != NULL) {
		nbuf->size = 0;
		nbuf->position = 0;
		nbuf->length = length;
		nbuf->buf = malloc(length);
	}
	return nbuf;
}

size_t asynchia_buffer_add(
	struct asynchia_buffer* buf, char* abuf, size_t length
) {
	size_t i;
	for (i = 0; i < asynchia_minsize(length, buf->length - buf->size); ++i) {
		buf->buf[buf->size + i] = abuf[i];
	}
	buf->size += i;
	return i;
}

size_t asynchia_buffer_send(
	struct asynchia_buffer* buf, int sockfd, int flags
) {
	size_t ret;
	int errsv;
	struct asynchia_send_ret mret;

	if (
	(ret = send(sockfd,
		buf->buf + buf->position,
		buf->size - buf->position,
		flags)) == -1) {
		errsv = errno;
	}
	buf->position += ret;

	mret.ret = ret;
	mret.errsv = errsv;
	return ret;
}

int main() {
	struct asynchia_buffer* buf = asynchia_buffer_new(20);
	printf("%d\n", asynchia_buffer_add(buf, "abcde", 5));
	asynchia_buffer_add(buf, "fghij", 5);
	asynchia_buffer_add(buf, "klmno", 5);
	asynchia_buffer_add(buf, "pqrst", 5);
	printf("%d\n", asynchia_buffer_add(buf, "foo", 3));
	return 0;
}
