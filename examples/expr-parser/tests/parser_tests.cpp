// Proof #3: C++ expression parser — parser unit tests (AST shape checks).
#include <cstdio>
#include <string>
#include <vector>

#include "expr/error.h"
#include "expr/lexer.h"
#include "expr/parser.h"
#include "expr/print.h"

namespace {

struct Case {
    std::string input;
    std::string expected_ast;  // print_ast output
};

const std::vector<Case> kCases = {
    {"2+3*4", "(+ 2 (* 3 4))"},
    {"10-3-2", "(- (- 10 3) 2)"},       // left assoc
    {"2^3^2", "(^ 2 (^ 3 2))"},         // right assoc
    {"-2^2", "(- (^ 2 2))"},            // unary binds looser than ^
    {"-(2+3)", "(- (+ 2 3))"},
    {"sin(x)", "(sin x)"},
    {"pow(2,3)", "(pow 2 3)"},
    {"sqrt(4)", "(sqrt 4)"},
    {"(2+3)*4", "(* (+ 2 3) 4)"},
    {"5*-3", "(* 5 (- 3))"},
    {"---5", "(- (- (- 5)))"},
    {"2.5e-1", "0.25"},
};

const std::vector<std::string> kErrorCases = {
    ")",       // dangling close paren
    "2+",      // trailing operator
    "2 3",     // trailing garbage
    "(2+3",    // missing closing paren
    "",        // empty input
};

} // namespace

int run_parser_tests() {
    int passed = 0;
    int failed = 0;

    for (const Case& c : kCases) {
        try {
            std::shared_ptr<expr::Node> node = expr::parse(expr::lex(c.input));
            std::string got = expr::print_ast(node);
            if (got == c.expected_ast) {
                ++passed;
            } else {
                std::printf("FAIL  parse(%s): got %s, expected %s\n",
                            c.input.c_str(), got.c_str(),
                            c.expected_ast.c_str());
                ++failed;
            }
        } catch (const expr::ParseError& e) {
            std::printf("FAIL  parse(%s): threw ParseError (%s)\n",
                        c.input.c_str(), e.message.c_str());
            ++failed;
        }
    }

    for (const std::string& bad : kErrorCases) {
        try {
            expr::parse(expr::lex(bad));
            std::printf("FAIL  parse(%s): expected ParseError, got a tree\n",
                        bad.c_str());
            ++failed;
        } catch (const expr::ParseError&) {
            ++passed;
        }
    }

    // Position sanity: "2+" error should point at end of input.
    try {
        expr::parse(expr::lex("2+"));
        std::printf("FAIL  parse(\"2+\") position check: no error thrown\n");
        ++failed;
    } catch (const expr::ParseError& e) {
        if (e.pos == 2) ++passed;
        else {
            std::printf("FAIL  parse(\"2+\") pos = %lu, expected 2\n",
                        (unsigned long)e.pos);
            ++failed;
        }
    }

    std::printf("parser tests: %d passed, %d failed\n", passed, failed);
    return failed == 0 ? 0 : 1;
}
