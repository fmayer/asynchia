#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/socket.h>

struct mysend_ret {
	ssize_t ret;
	int errsv;
};

struct asynchia_buffer {
	ssize_t size;
	ssize_t length;
	ssize_t position;
	char* buf;
};

int expand(struct asynchia_buffer* buf, ssize_t n) {
	char* nbuf = realloc(buf->buf, buf->length + n);
	if (nbuf != NULL) {
		buf->buf = nbuf;
		buf->length = buf->length + n;
		return 0;
	} else {
		return -1;
	}
}

struct asynchia_buffer* new_buffer(ssize_t length) {
	struct asynchia_buffer* nbuf = malloc(sizeof(struct asynchia_buffer));
	if (nbuf != NULL) {
		nbuf->size = 0;
		nbuf->position = 0;
		nbuf->length = length;
		nbuf->buf = malloc(length);
	}
	return nbuf;
}

ssize_t add(struct asynchia_buffer* buf, char* abuf, ssize_t length) {
	ssize_t i;
	for (i = 0; i < min(length, buf->length - buf->size); ++i) {
		buf->buf[buf->size + i] = abuf[i];
	}
	buf->size += i;
	return 0;
}

ssize_t mysend(struct asynchia_buffer* buf, int sockfd, int flags) {
	ssize_t ret;
	int errsv;
	struct mysend_ret mret;

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
	struct asynchia_buffer* buf = new_buffer(20);
	printf("%d\n", add(buf, "abcde", 5));
	add(buf, "fghij", 5);
	add(buf, "klmno", 5);
	add(buf, "pqrst", 5);
	printf("%d\n", add(buf, "foo", 3));
	return 0;
}
