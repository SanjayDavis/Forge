// Proof #3: C++ expression parser — REPL and single-shot CLI.
#include <cstdio>
#include <iostream>
#include <string>

#include "expr/context.h"
#include "expr/error.h"
#include "expr/evaluator.h"
#include "expr/lexer.h"
#include "expr/parser.h"
#include "expr/print.h"

namespace expr_cli {

// Evaluate one expression. Returns true on success (out = result),
// false on failure (out = rendered error).
bool eval_string(const std::string& line, const expr::Context& ctx,
                 std::string& out) {
    try {
        std::shared_ptr<expr::Node> node = expr::parse(expr::lex(line));
        const double v = expr::eval(node, ctx);
        char buf[64];
        std::snprintf(buf, sizeof buf, "%.12g", v);
        out = buf;
        return true;
    } catch (const expr::ParseError& e) {
        out = expr::render_error(line, e);
        return false;
    } catch (const expr::EvalError& e) {
        out = e.message;
        return false;
    }
}

} // namespace expr_cli

int main(int argc, char** argv) {
    expr::Context ctx;

    // Single-shot mode: ./expr "2+3" -> print result, exit 0; errors exit 1.
    if (argc >= 2) {
        std::string text = argv[1];
        for (int i = 2; i < argc; ++i) {
            text += " ";
            text += argv[i];
        }
        std::string out;
        if (expr_cli::eval_string(text, ctx, out)) {
            std::printf("%s\n", out.c_str());
            return 0;
        }
        std::fprintf(stderr, "%s\n", out.c_str());
        return 1;
    }

    // Interactive REPL.
    std::string line;
    for (;;) {
        std::printf("> ");
        std::fflush(stdout);
        if (!std::getline(std::cin, line)) break;  // EOF
        if (line == "quit" || line == "exit") break;
        if (line.empty()) continue;

        if (line.rfind(":ast ", 0) == 0) {
            const std::string body = line.substr(5);
            try {
                std::printf("%s\n",
                            expr::print_ast(expr::parse(expr::lex(body))).c_str());
            } catch (const expr::ParseError& e) {
                std::printf("%s\n", expr::render_error(body, e).c_str());
            }
            continue;
        }

        std::string out;
        expr_cli::eval_string(line, ctx, out);
        std::printf("%s\n", out.c_str());
    }
    return 0;
}
