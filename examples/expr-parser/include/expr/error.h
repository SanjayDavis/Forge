// Proof #3: C++ expression parser — positioned errors.
#ifndef EXPR_ERROR_H
#define EXPR_ERROR_H

#include <cstddef>
#include <exception>
#include <string>
#include <utility>

namespace expr {

struct ParseError : std::exception {
    std::string message;
    std::size_t pos;

    ParseError(std::string msg, std::size_t p)
        : message(std::move(msg)), pos(p) {}

    const char* what() const noexcept override { return message.c_str(); }
};

struct EvalError : std::exception {
    std::string message;

    explicit EvalError(std::string msg) : message(std::move(msg)) {}

    const char* what() const noexcept override { return message.c_str(); }
};

// Render a parse error with a caret pointing at the offending column.
inline std::string render_error(const std::string& source, const ParseError& e) {
    std::string out = e.message;
    out += "\n" + source + "\n";
    for (std::size_t i = 0; i < e.pos; ++i) out += ' ';
    out += "^\n(at column " + std::to_string(e.pos) + ")";
    return out;
}

} // namespace expr

#endif // EXPR_ERROR_H
