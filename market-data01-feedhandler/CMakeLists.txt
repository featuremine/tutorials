#[===[
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.

        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
]===]


add_subproject(
    NAME json
    VERSION "v3.11.2"
    GIT_REVISION "v3.11.2"
    GIT_URL "https://github.com/nlohmann/json.git"
    TARGETS json
)

git_clone(
    GIT_REVISION master
    GIT_URL "https://github.com/dhbaird/easywsclient.git"
    DIR ${CMAKE_BINARY_DIR}/dependencies/src/easywsclient
)
add_library(
    easywsclient
    STATIC
    ${CMAKE_BINARY_DIR}/dependencies/src/easywsclient/easywsclient.cpp
)
target_include_directories(
    easywsclient
    PUBLIC
    "${CMAKE_BINARY_DIR}/dependencies/src/easywsclient"
)

add_executable(
    binance-feed
    "binance-feed.cpp"
)
target_link_libraries(
    binance-feed
    PRIVATE
    easywsclient
)