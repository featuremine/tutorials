# Introduction

To facilitate tutorials, we've created a repository containing all of the relevant code. The repositiory also contains various tools for argorithmic trading.

Before diving in, ensure you've installed [git](https://git-scm.com/downloads), [CMake](https://cmake.org/download), C++ compiler toolchain and set up your favorite development environment. For example, [here](https://code.visualstudio.com/docs/languages/cpp) is the reference on how to set up Visual Studio Code. This project is compatible with contemporary Linux and MacOS setups. For Windows users, consider using either the Windows Subsystem for Linux (WSL) or a Docker container.

## Building

Kick off by cloning the tutorial repository, setting up the build directory and running the build:
```bash
git clone --recurse-submodules https://github.com/featuremine/tutorials
cd tutorials
cmake -B release -DCMAKE_BUILD_TYPE=Release
cmake --build release
```
Post-build, you should be able to find the tutorial binaries under **release**. Each tutorial is located in its own directory for example **market-data01-feedhandler**. All of the relevant sources are in the correspoinding tutorial directory.

[Continue reading...](docs/README.md)
