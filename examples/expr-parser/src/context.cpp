// Proof #3: C++ expression parser — context implementation.
#include "expr/context.h"

namespace expr {

Context::Context() {
    builtins_["sin"]    = [](double x) { return std::sin(x); };
    builtins_["cos"]    = [](double x) { return std::cos(x); };
    builtins_["tan"]    = [](double x) { return std::tan(x); };
    builtins_["asin"]   = [](double x) { return std::asin(x); };
    builtins_["acos"]   = [](double x) { return std::acos(x); };
    builtins_["atan"]   = [](double x) { return std::atan(x); };
    builtins_["sqrt"]   = [](double x) { return std::sqrt(x); };
    builtins_["cbrt"]   = [](double x) { return std::cbrt(x); };
    builtins_["abs"]    = [](double x) { return std::fabs(x); };
    builtins_["log"]    = [](double x) { return std::log(x); };
    builtins_["log10"]  = [](double x) { return std::log10(x); };
    builtins_["exp"]    = [](double x) { return std::exp(x); };
    builtins_["floor"]  = [](double x) { return std::floor(x); };
    builtins_["ceil"]   = [](double x) { return std::ceil(x); };
    builtins_["round"]  = [](double x) { return std::round(x); };

    vars_["pi"] = 3.14159265358979323846;
    vars_["e"]  = 2.71828182845904523536;
}

} // namespace expr
