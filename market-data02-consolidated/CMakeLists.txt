#[===[
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.

        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
]===]

add_library(
    feed-handler
    SHARED
    "feed-handler.cpp"
    "kraken-feed-handler.cpp"
)
target_link_libraries(
    feed-handler
    PRIVATE
    websockets ${LIBWEBSOCKETS_DEP_LIBS}
    fmc++ ytp
)
set_target_properties(
    feed-handler
    PROPERTIES
    LIBRARY_OUTPUT_NAME "feed_handler"
    PREFIX ""
)

add_library(
    feed-parser
    SHARED
    "feed-parser.cpp"
)
target_link_libraries(
    feed-parser
    PRIVATE
    websockets ${LIBWEBSOCKETS_DEP_LIBS}
    fmc++ ytp
)
set_target_properties(
    feed-parser
    PROPERTIES
    LIBRARY_OUTPUT_NAME "feed_parser"
    PREFIX ""
)
