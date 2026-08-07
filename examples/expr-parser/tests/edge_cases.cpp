// Proof #3: C++ expression parser — edge-case / stress tests.
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "expr/context.h"
#include "expr/error.h"
#include "expr/evaluator.h"
#include "expr/lexer.h"
#include "expr/parser.h"
#include "expr/print.h"

namespace {

int g_passed = 0;
int g_failed = 0;

void check_ok(const std::string& in, const expr::Context& ctx, double expected,
              double tol) {
    try {
        double v = expr::eval(expr::parse(expr::lex(in)), ctx);
        if (std::fabs(v - expected) <= tol) ++g_passed;
        else {
            std::printf("FAIL  %s = %g, expected %g\n", in.c_str(), v, expected);
            ++g_failed;
        }
    } catch (const std::exception& e) {
        std::printf("FAIL  %s threw: %s\n", in.c_str(), e.what());
        ++g_failed;
    }
}

void expect_no_crash(const std::string& in, const expr::Context& ctx) {
    // The point is: no crash, no hang, clean error or value.
    try {
        expr::eval(expr::parse(expr::lex(in)), ctx);
    } catch (const std::exception&) {
    } catch (...) {
        std::printf("FAIL  %s threw non-std exception (unexpected)\n",
                    in.c_str());
        ++g_failed;
        return;
    }
    ++g_passed;
}

void expect_parse_error(const std::string& in) {
    try {
        expr::parse(expr::lex(in));
        std::printf("FAIL  parse(%s): expected ParseError\n", in.c_str());
        ++g_failed;
    } catch (const expr::ParseError&) {
        ++g_passed;
    }
}

} // namespace

int run_edge_case_tests() {
    expr::Context ctx;

    // Deep nesting: 50 nested parens around 1 -> evaluates to 1.
    {
        std::string in;
        for (int i = 0; i < 50; ++i) in += "(";
        in += "1";
        for (int i = 0; i < 50; ++i) in += ")";
        check_ok(in, ctx, 1.0, 0.0);
    }

    // Long chain 1+2+...+100 == 5050.
    {
        std::string in = "1";
        for (int i = 2; i <= 100; ++i) {
            in += "+";
            in += std::to_string(i);
        }
        check_ok(in, ctx, 5050.0, 1e-6);
    }

    // Stress cases.
    check_ok("---5", ctx, -5.0, 0.0);          // unary chain
    check_ok("5*-3", ctx, -15.0, 0.0);
    check_ok("1e-3", ctx, 0.001, 0.0);
    check_ok("2.5e2", ctx, 250.0, 0.0);
    check_ok("7%3", ctx, 1.0, 0.0);
    check_ok("-7%3", ctx, -1.0, 0.0);          // fmod semantics
    check_ok("sin(0)+cos(0)", ctx, 1.0, 1e-12);
    check_ok("sqrt(2)*sqrt(2)", ctx, 2.0, 1e-9);
    check_ok("abs(-0.5)*(-2)", ctx, -1.0, 1e-12);

    // Big value: evaluates, doesn't overflow to inf (1e308 stays finite).
    {
        double v = expr::eval(expr::parse(expr::lex("1e308")), ctx);
        if (std::isfinite(v)) ++g_passed;
        else {
            std::printf("FAIL  1e308 not finite\n");
            ++g_failed;
        }
    }

    // Nested function calls and mixed expressions.
    check_ok("floor(2.7)+ceil(2.1)", ctx, 5.0, 0.0);
    check_ok("log10(1000)", ctx, 3.0, 1e-12);
    check_ok("exp(log(e))", ctx, 2.718281828459045, 1e-9);

    // Malformed input must not crash.
    expect_no_crash("", ctx);
    expect_no_crash("   ", ctx);
    expect_no_crash("2 3", ctx);
    expect_no_crash("(()", ctx);
    expect_no_crash("sqrt(1", ctx);
    expect_no_crash("1e", ctx);      // "1" then identifier "e"
    expect_no_crash("$", ctx);
    expect_no_crash("2+2*", ctx);

    // sqrt(-1) -> NaN is fine (matches IEEE), must not crash.
    {
        double v = expr::eval(expr::parse(expr::lex("sqrt(-1)")), ctx);
        (void)v;  // no throw is the bar
        ++g_passed;
    }

    // Whitespace-heavy input.
    check_ok("  2  +\t 3 *\n 4  ", ctx, 14.0, 0.0);

    std::printf("edge-case tests: %d passed, %d failed\n", g_passed, g_failed);
    return g_failed == 0 ? 0 : 1;
}