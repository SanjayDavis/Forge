// Proof #3: C++ expression parser — evaluator implementation.
#include "expr/evaluator.h"

#include <cmath>
#include <string>

#include "expr/error.h"

namespace expr {

double eval(const std::shared_ptr<Node>& node, const Context& ctx) {
    switch (node->kind) {
        case Node::Number:
            return node->number;

        case Node::Variable:
            if (!ctx.has_var(node->name)) {
                throw EvalError("unknown variable '" + node->name + "'");
            }
            return ctx.value(node->name);

        case Node::Unary: {
            const double v = eval(node->left, ctx);
            return node->op == '-' ? -v : v;
        }

        case Node::Binary: {
            const double l = eval(node->left, ctx);
            const double r = eval(node->right, ctx);
            switch (node->op) {
                case '+': return l + r;
                case '-': return l - r;
                case '*': return l * r;
                case '/':
                    if (r == 0.0) throw EvalError("division by zero");
                    return l / r;
                case '%':
                    if (r == 0.0) throw EvalError("modulo by zero");
                    return std::fmod(l, r);
                case '^': return std::pow(l, r);
            }
            throw EvalError("invalid binary operator");
        }

        case Node::Call: {
            if (node->name == "pow") {
                if (node->args.size() != 2) {
                    throw EvalError("pow expects 2 arguments");
                }
                return std::pow(eval(node->args[0], ctx),
                                eval(node->args[1], ctx));
            }
            if (node->args.size() != 1) {
                throw EvalError(node->name + " expects 1 argument");
            }
            if (!ctx.has_builtin(node->name)) {
                throw EvalError("unknown function '" + node->name + "'");
            }
            return ctx.call_builtin(node->name, eval(node->args[0], ctx));
        }
    }
    throw EvalError("invalid node");
}

} // namespace expr
