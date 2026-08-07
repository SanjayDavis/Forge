# Proof #3: C++ expression parser — build system.
# GCC 6.3 / MinGW-friendly: plain make, C++14, no cmake.
# Sources are picked up via wildcards so the build works as tasks land.

CXX      = g++
CXXFLAGS = -std=c++14 -Wall -Wextra -Iinclude

# src/main.cpp holds the CLI; core = everything else (compiled into both binaries).
CORE_SRC = $(filter-out src/main.cpp,$(wildcard src/*.cpp))
CORE_OBJ = $(CORE_SRC:.cpp=.o)
MAIN_OBJ = src/main.o

TEST_SRC = $(wildcard tests/*.cpp)
TEST_OBJ = $(TEST_SRC:.cpp=.o)

all: expr

expr: $(MAIN_OBJ) $(CORE_OBJ)
	$(CXX) $(CXXFLAGS) -o $@ $(MAIN_OBJ) $(CORE_OBJ)

expr_tests: $(CORE_OBJ) $(TEST_OBJ)
	$(CXX) $(CXXFLAGS) -o $@ $(CORE_OBJ) $(TEST_OBJ)

test: expr expr_tests
	./expr_tests

clean:
	rm -f expr expr_tests src/*.o tests/*.o

.PHONY: all test clean
