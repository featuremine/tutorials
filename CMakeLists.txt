#[===[
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.

        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
]===]

cmake_minimum_required(VERSION 3.15)

file (STRINGS "VERSION" TUTORIALS_VERSION)

project(
    tutorials
    VERSION "${TUTORIALS_VERSION}"
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

find_package(OpenSSL REQUIRED)
add_subproject(
    NAME yamal
    VERSION "8.0.8"
    GIT_REVISION "v8.0.8"
    GIT_URL "https://github.com/featuremine/yamal.git"
    TARGETS fmc++ ytp yamal-tail yamal-local-perf yamal-stats
)
SET(LWS_STATIC_PIC ON)
add_subproject(
    NAME websockets
    GIT_REVISION "v4.3.2"
    GIT_URL "https://github.com/warmcat/libwebsockets.git"
    TARGETS websockets
)

add_custom_target(
    tutorial-utils ALL
    DEPENDS
    yamal-tail
    yamal-local-perf
    yamal-stats
)

if (BUILD_DOCUMENTATION)
    set(FmDocumentation_DIR "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
    find_package(FmDocumentation REQUIRED)
    add_documentation(
        NAME tutorials-docs
        BUILD_DIR "${CMAKE_CURRENT_BINARY_DIR}/docs"
        SRC_DIR "${CMAKE_CURRENT_SOURCE_DIR}/docs"
        TITLE "Tutorials"
        VERSION "${PROJECT_VERSION}"
    )
endif()

set(FmConfig_DIR "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
find_package(FmConfig REQUIRED)
fm_config()

set(package_DEP "")
set(package_FILES "")
macro(add_bin_to_package TARGET)
    add_custom_command(
        OUTPUT
        "${PROJECT_BINARY_DIR}/package/bin/${TARGET}${CMAKE_EXECUTABLE_SUFFIX}"

        COMMAND
        ${CMAKE_COMMAND} -E copy
        "$<TARGET_FILE:${TARGET}>"
        "${PROJECT_BINARY_DIR}/package/bin/${TARGET}${CMAKE_EXECUTABLE_SUFFIX}"

        DEPENDS
        ${TARGET}
    )
    list(APPEND package_DEP "${PROJECT_BINARY_DIR}/package/bin/${TARGET}${CMAKE_EXECUTABLE_SUFFIX}")
    list(APPEND package_FILES "${PROJECT_BINARY_DIR}/package/bin/${TARGET}${CMAKE_EXECUTABLE_SUFFIX}")
endmacro()

macro(add_component_to_package TARGET)
    add_custom_command(
        OUTPUT
        "${PROJECT_BINARY_DIR}/package/lib/yamal/modules/${TARGET}${CMAKE_SHARED_LIBRARY_SUFFIX}"

        COMMAND
        ${CMAKE_COMMAND} -E copy
        "$<TARGET_FILE:${TARGET}>"
        "${PROJECT_BINARY_DIR}/package/lib/yamal/modules/${TARGET}${CMAKE_SHARED_LIBRARY_SUFFIX}"

        DEPENDS
        ${TARGET}
    )
    list(APPEND package_DEP "${PROJECT_BINARY_DIR}/package/lib/yamal/modules/${TARGET}${CMAKE_SHARED_LIBRARY_SUFFIX}")
    list(APPEND package_FILES "${PROJECT_BINARY_DIR}/package/lib/yamal/modules/${TARGET}${CMAKE_SHARED_LIBRARY_SUFFIX}")
endmacro()

add_subdirectory(market-data01-feedhandler)
add_bin_to_package(minimal-ws-client-binance)
add_component_to_package(binance_feed_handler)

add_subdirectory(market-data02-consolidated)
add_component_to_package(feed_handler)
add_component_to_package(kraken_feed_handler)
add_component_to_package(feed_parser)

file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/output")
add_custom_command(
    OUTPUT
    "${CMAKE_BINARY_DIR}/output/tutorials-${PROJECT_VERSION}-${CMAKE_SYSTEM_NAME}-${CMAKE_SYSTEM_PROCESSOR}.tar.gz"

    COMMAND
    ${CMAKE_COMMAND} -E chdir "${CMAKE_CURRENT_BINARY_DIR}/package"
    ${CMAKE_COMMAND} -E tar "czvf" "${CMAKE_BINARY_DIR}/output/tutorials-${PROJECT_VERSION}-${CMAKE_SYSTEM_NAME}-${CMAKE_SYSTEM_PROCESSOR}.tar.gz"
    ${package_FILES}

    DEPENDS
    ${package_DEP}
)

add_custom_target(
    tutorials-package ALL
    DEPENDS "${CMAKE_BINARY_DIR}/output/tutorials-${PROJECT_VERSION}-${CMAKE_SYSTEM_NAME}-${CMAKE_SYSTEM_PROCESSOR}.tar.gz"
)
