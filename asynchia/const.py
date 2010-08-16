import errno

trylater = (errno.EAGAIN,)
connection_lost = (errno.ECONNRESET, errno.ECONNABORTED)