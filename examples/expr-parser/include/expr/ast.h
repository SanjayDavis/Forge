// Proof #3: C++ expression parser — AST nodes.
// C++14-safe (GCC 6.3): tagged struct with shared_ptr children, no std::variant.
#ifndef EXPR_AST_H
#define EXPR_AST_H

#include <memory>
#include <string>
#include <utility>
#include <vector>

namespace expr {

struct Node {
    enum Kind { Number, Variable, Unary, Binary, Call } kind;

    double number = 0.0;                                  // Number
    std::string name;                                     // Variable / Call callee
    char op = 0;                                          // Unary / Binary operator
    std::shared_ptr<Node> left;                           // Unary operand / Binary lhs
    std::shared_ptr<Node> right;                          // Binary rhs
    std::vector<std::shared_ptr<Node>> args;              // Call arguments
};

inline std::shared_ptr<Node> make_number(double v) {
    auto n = std::make_shared<Node>();
    n->kind = Node::Number;
    n->number = v;
    return n;
}

inline std::shared_ptr<Node> make_variable(std::string name) {
    auto n = std::make_shared<Node>();
    n->kind = Node::Variable;
    n->name = std::move(name);
    return n;
}

inline std::shared_ptr<Node> make_unary(char op, std::shared_ptr<Node> operand) {
    auto n = std::make_shared<Node>();
    n->kind = Node::Unary;
    n->op = op;
    n->left = std::move(operand);
    return n;
}

inline std::shared_ptr<Node> make_binary(char op, std::shared_ptr<Node> l,
                                         std::shared_ptr<Node> r) {
    auto n = std::make_shared<Node>();
    n->kind = Node::Binary;
    n->op = op;
    n->left = std::move(l);
    n->right = std::move(r);
    return n;
}

inline std::shared_ptr<Node> make_call(std::string name,
                                       std::vector<std::shared_ptr<Node>> args) {
    auto n = std::make_shared<Node>();
    n->kind = Node::Call;
    n->name = std::move(name);
    n->args = std::move(args);
    return n;
}

} // namespace expr

#endif // EXPR_AST_H
