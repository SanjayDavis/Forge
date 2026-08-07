// Proof #3: C++ expression parser — evaluator pipeline tests (lex->parse->eval).
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

#include "expr/context.h"
#include "expr/error.h"
#include "expr/evaluator.h"
#include "expr/lexer.h"
#include "expr/parser.h"

namespace {

struct Case {
    std::string input;
    double expected;
    double tol;
};

const std::vector<Case> kCases = {
    {"2+2", 4.0, 0.0},
    {"10-3-2", 5.0, 0.0},
    {"3*4+5", 17.0, 0.0},
    {"2^10", 1024.0, 0.0},
    {"2^3^2", 512.0, 0.0},
    {"sqrt(9)", 3.0, 0.0},
    {"abs(-4)", 4.0, 0.0},
    {"sin(0)", 0.0, 1e-12},
    {"pi*2", 6.283185307179586, 1e-12},
    {"5%2", 1.0, 0.0},
    {"2+3*4", 14.0, 0.0},
    {"-2^2", -4.0, 0.0},
    {"pow(2,3)", 8.0, 0.0},
    {"sqrt(abs(-9))", 3.0, 0.0},
    {"sin(0)+cos(0)", 1.0, 1e-12},
    {"e", 2.718281828459045, 1e-12},
    {"sqrt(2)^2", 2.0, 1e-9},
    {"100/10/2", 5.0, 0.0},   // left assoc division
};

struct ErrCase {
    std::string input;
    std::string fragment;  // substring the EvalError message must contain
};

const std::vector<ErrCase> kErrCases = {
    {"1/0", "division by zero"},
    {"1%0", "modulo by zero"},
    {"zzz", "unknown variable"},
    {"nosuchfn(1)", "unknown function"},
    {"pow(2)", "expects 2 arguments"},
    {"sqrt(1,2)", "expects 1 argument"},
};

} // namespace

int run_evaluator_tests() {
    int passed = 0;
    int failed = 0;
    expr::Context ctx;
    ctx["x"] = 21.0;

    for (const Case& c : kCases) {
        try {
            double got = expr::eval(expr::parse(expr::lex(c.input)), ctx);
            if (std::fabs(got - c.expected) <= c.tol) {
                ++passed;
            } else {
                std::printf("FAIL  eval(%s) = %g, expected %g\n",
                            c.input.c_str(), got, c.expected);
                ++failed;
            }
        } catch (const std::exception& e) {
            std::printf("FAIL  eval(%s) threw: %s\n", c.input.c_str(), e.what());
            ++failed;
        }
    }

    // Variable from context.
    try {
        double got = expr::eval(expr::parse(expr::lex("x*2")), ctx);
        if (got == 42.0) ++passed;
        else {
            std::printf("FAIL  eval(x*2) = %g, expected 42\n", got);
            ++failed;
        }
    } catch (const std::exception& e) {
        std::printf("FAIL  eval(x*2) threw: %s\n", e.what());
        ++failed;
    }

    for (const ErrCase& c : kErrCases) {
        try {
            expr::eval(expr::parse(expr::lex(c.input)), ctx);
            std::printf("FAIL  eval(%s): expected EvalError, got a value\n",
                        c.input.c_str());
            ++failed;
        } catch (const expr::EvalError& e) {
            if (std::string(e.what()).find(c.fragment) != std::string::npos) {
                ++passed;
            } else {
                std::printf("FAIL  eval(%s): message '%s' lacks '%s'\n",
                            c.input.c_str(), e.what(), c.fragment.c_str());
                ++failed;
            }
        }
    }

    std::printf("evaluator tests: %d passed, %d failed\n", passed, failed);
    return failed == 0 ? 0 : 1;
}
