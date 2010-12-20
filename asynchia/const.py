import errno

trylater = (errno.EAGAIN,)
connection_lost = (errno.ECONNRESET, errno.ECONNABORTED)
inprogress = (errno.EINPROGRESS, errno.EWOULDBLOCK)
