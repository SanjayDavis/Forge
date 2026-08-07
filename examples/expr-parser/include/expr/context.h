// Proof #3: C++ expression parser — variable context and builtin functions.
#ifndef EXPR_CONTEXT_H
#define EXPR_CONTEXT_H

#include <cmath>
#include <functional>
#include <map>
#include <string>

namespace expr {

class Context {
public:
    Context();

    double& operator[](const std::string& name) { return vars_[name]; }
    double value(const std::string& name) const { return vars_.at(name); }
    bool has_var(const std::string& name) const { return vars_.count(name) != 0; }

    bool has_builtin(const std::string& name) const { return builtins_.count(name) != 0; }
    double call_builtin(const std::string& name, double x) const {
        return builtins_.at(name)(x);
    }
    std::size_t builtin_count() const { return builtins_.size(); }

private:
    std::map<std::string, std::function<double(double)>> builtins_;
    std::map<std::string, double> vars_;
};

} // namespace expr

#endif // EXPR_CONTEXT_H
