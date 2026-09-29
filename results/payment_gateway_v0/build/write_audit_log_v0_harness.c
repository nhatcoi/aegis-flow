#include <stdio.h>
int write_audit_log(void);
int main(void) { printf("rc=%d\n", write_audit_log()); return 0; }
