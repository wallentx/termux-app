#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <netdb.h>
#include <spawn.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>
extern char **environ;
int main(int argc,char **argv) {
    if(argc>1 && !strcmp(argv[1],"--child"))return 37;
    char path[4096]={0};ssize_t n=readlink("/proc/self/exe",path,sizeof(path)-1);assert(n>0);path[n]=0;
    printf("UID=%ld EXE=%s\n",(long)getuid(),path);
    assert(strstr(path,"aether-probe"));
    FILE *f=fopen("/etc/resolv.conf","r");assert(f);char line[256];assert(fgets(line,sizeof(line),f));fclose(f);puts("resolv.conf readable");
    struct addrinfo hints={0},*result=NULL;hints.ai_socktype=SOCK_STREAM;hints.ai_flags=AI_CANONNAME;
    int rc=getaddrinfo("browser.geekbench.com","443",&hints,&result);printf("DNS=%d\n",rc);assert(rc==0 && result);freeaddrinfo(result);
    hints.ai_flags=AI_NUMERICHOST;rc=getaddrinfo("not-a-numeric-address.invalid","443",&hints,&result);assert(rc==EAI_NONAME);
    rc=getaddrinfo("127.0.0.1","443",&hints,&result);assert(rc==0 && result);freeaddrinfo(result);
    puts("DNS success, numeric, and failure semantics passed");
    char *child[]={path,"--child",NULL};pid_t pid=fork();assert(pid>=0);
    if(!pid) { execve(path,child,environ);perror("execve");_exit(125); }
    int status;assert(waitpid(pid,&status,0)==pid && WIFEXITED(status) && WEXITSTATUS(status)==37);puts("execve child passed");
    rc=posix_spawn(&pid,path,NULL,NULL,child,environ);assert(!rc);
    assert(waitpid(pid,&status,0)==pid && WIFEXITED(status) && WEXITSTATUS(status)==37);puts("posix_spawn child passed");
    puts("AETHER_PROBE_PASS");return 0;
}
