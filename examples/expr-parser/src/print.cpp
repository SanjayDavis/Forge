// Proof #3: C++ expression parser — AST pretty printer implementation.
#include "expr/print.h"

#include <cstdio>

namespace expr {

namespace {

void append_number(std::string& out, double v) {
    char buf[64];
    std::snprintf(buf, sizeof buf, "%g", v);
    out += buf;
}

void append(std::string& out, const std::shared_ptr<Node>& n) {
    switch (n->kind) {
        case Node::Number:
            append_number(out, n->number);
            break;
        case Node::Variable:
            out += n->name;
            break;
        case Node::Unary:
            out += "(";
            out += n->op;
            out += " ";
            append(out, n->left);
            out += ")";
            break;
        case Node::Binary:
            out += "(";
            out += n->op;
            out += " ";
            append(out, n->left);
            out += " ";
            append(out, n->right);
            out += ")";
            break;
        case Node::Call:
            out += "(";
            out += n->name;
            for (const auto& a : n->args) {
                out += " ";
                append(out, a);
            }
            out += ")";
            break;
    }
}

} // namespace

std::string print_ast(const std::shared_ptr<Node>& node) {
    std::string out;
    append(out, node);
    return out;
}

} // namespace expr
