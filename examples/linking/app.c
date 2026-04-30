#include <stdio.h>
#include <stdlib.h>
#include "mathlib.h"

int main(int argc, char *argv[]) {
    int a = 3, b = 4;
    if (argc == 3) {
        a = atoi(argv[1]);
        b = atoi(argv[2]);
    }
    printf("%d + %d = %d\n", a, b, add(a, b));
    printf("%d * %d = %d\n", a, b, multiply(a, b));
    return 0;
}
