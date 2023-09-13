#[===[
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.

        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
]===]

cmake_minimum_required(VERSION 3.15)

file (STRINGS "VERSION" TUTORIAL_VERSION)

project(
    tutorials
    VERSION "${TUTORIAL_VERSION}"
    DESCRIPTION "Featuremine tutorials"
    HOMEPAGE_URL "https://www.featuremine.com"
)

set(Subproject_DIR "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
find_package(Subproject REQUIRED)

option (BUILD_SHARED_LIBS "Request build of shared libraries." ON)
option (BUILD_TESTING "Enable build of the unit tests and their execution." ON)
option (BUILD_TOOLS "Enable build of command line tools." ON)
option (BUILD_WHEEL "Enable build of the python package." ON)
option (TEST_EXTENSIONS "Enable testing the extensions." ON)

add_subproject(
    NAME yamal
    VERSION "8.0.2"
    GIT_REVISION "improve-cmdline"
    GIT_URL "https://github.com/featuremine/yamal.git"
    TARGETS fmc++ ytp yamal-tail yamal-local-perf
)

add_custom_target(
    tutorial-utils ALL
    DEPENDS
    yamal-tail
    yamal-local-perf
)

set(FmConfig_DIR "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
find_package(FmConfig REQUIRED)
fm_config()

add_subdirectory(market-data01-feedhandler)