// Proof #3: C++ expression parser — test runner main.
// Aggregates every suite; each run_<suite>_tests returns 0 on success.
#include <cstdio>

int run_lexer_tests();
int run_parser_tests();
int run_evaluator_tests();
int run_cli_tests();
int run_edge_case_tests();

int main() {
    int failed = 0;
    failed += run_lexer_tests();
    failed += run_parser_tests();
    failed += run_evaluator_tests();
    failed += run_cli_tests();
    failed += run_edge_case_tests();
    if (failed) {
        std::printf("test run FAILED (%d suite(s) failed)\n", failed);
        return 1;
    }
    std::printf("all test suites passed\n");
    return 0;
}